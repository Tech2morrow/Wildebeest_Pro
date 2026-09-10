#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "BatterySafety.h"
#include "Config.h"
#include "MotorController.h"
#include "Protocol.h"

namespace {

volatile int32_t leftTicks = 0;
volatile int32_t rightTicks = 0;

wb::LineReceiver receiver;
wb::WheelController leftMotor(wb::LEFT_PWM_PIN, wb::LEFT_IN1_PIN, wb::LEFT_IN2_PIN,
                              wb::LEFT_MOTOR_INVERTED);
wb::WheelController rightMotor(wb::RIGHT_PWM_PIN, wb::RIGHT_IN1_PIN, wb::RIGHT_IN2_PIN,
                               wb::RIGHT_MOTOR_INVERTED);

uint16_t telemetrySequence = 0;
uint16_t statusFlags = wb::FLAG_WATCHDOG;
unsigned long lastCommandMs = 0;
unsigned long lastControlMs = 0;
unsigned long lastOdomMs = 0;
unsigned long lastImuMs = 0;
unsigned long lastRangeMs = 0;
unsigned long lastBatteryMs = 0;
unsigned long protocolFaultUntilMs = 0;

float requestedLeftRadS = 0.0F;
float requestedRightRadS = 0.0F;
float rampedLeftRadS = 0.0F;
float rampedRightRadS = 0.0F;
float measuredLeftRadS = 0.0F;
float measuredRightRadS = 0.0F;
int32_t previousLeftTicks = 0;
int32_t previousRightTicks = 0;
uint16_t batteryMv = 0;
uint16_t frontRangeMm = 0;
bool softEstop = false;
bool imuAvailable = false;
// Fail closed until the first valid battery sample only when the optional
// cutoff is explicitly compiled in.
bool lowVoltageMotorStopActive = wb::ENABLE_LOW_VOLTAGE_MOTOR_STOP;

enum class RangePhase : uint8_t { IDLE, TRIGGER_HIGH, WAIT_RISE, WAIT_FALL };
RangePhase rangePhase = RangePhase::IDLE;
unsigned long rangePhaseStartedUs = 0;
unsigned long echoStartedUs = 0;

void leftEncoderIsr() {
  const bool direction = digitalRead(wb::LEFT_ENCODER_A_PIN) == digitalRead(wb::LEFT_ENCODER_B_PIN);
  leftTicks += (direction ^ wb::LEFT_ENCODER_INVERTED) ? 1 : -1;
}

void rightEncoderIsr() {
  const bool direction = digitalRead(wb::RIGHT_ENCODER_A_PIN) == digitalRead(wb::RIGHT_ENCODER_B_PIN);
  rightTicks += (direction ^ wb::RIGHT_ENCODER_INVERTED) ? 1 : -1;
}

void snapshotTicks(int32_t& left, int32_t& right) {
  noInterrupts();
  left = leftTicks;
  right = rightTicks;
  interrupts();
}

bool elapsed(unsigned long now, unsigned long then, unsigned long period) {
  return static_cast<unsigned long>(now - then) >= period;
}

void sendError(uint16_t sequence, const char* code) {
  char body[64];
  snprintf(body, sizeof(body), "ERR,%u,%s", sequence, code);
  wb::writeFrame(Serial, body);
}

void markProtocolFault() {
  statusFlags |= wb::FLAG_PROTOCOL_ERROR;
  protocolFaultUntilMs = millis() + 1000UL;
}

bool parseCommand(char* body) {
  char* save = nullptr;
  const char* type = strtok_r(body, ",", &save);
  const char* sequenceText = strtok_r(nullptr, ",", &save);
  long sequenceLong = 0;
  if (type == nullptr || !wb::parseLongStrict(sequenceText, 0, 65535, sequenceLong)) return false;
  const uint16_t sequence = static_cast<uint16_t>(sequenceLong);

  if (strcmp(type, "CMD") == 0) {
    const char* linearText = strtok_r(nullptr, ",", &save);
    const char* angularText = strtok_r(nullptr, ",", &save);
    long linear = 0;
    long angular = 0;
    if (!wb::parseLongStrict(linearText, -wb::MAX_LINEAR_MM_S, wb::MAX_LINEAR_MM_S, linear) ||
        !wb::parseLongStrict(angularText, -wb::MAX_ANGULAR_MRAD_S,
                            wb::MAX_ANGULAR_MRAD_S, angular) ||
        strtok_r(nullptr, ",", &save) != nullptr) {
      sendError(sequence, "RANGE");
      return false;
    }
    const float linearMps = static_cast<float>(linear) / 1000.0F;
    const float angularRadS = static_cast<float>(angular) / 1000.0F;
    requestedLeftRadS = (linearMps - angularRadS * wb::WHEEL_SEPARATION_M * 0.5F) /
                        wb::WHEEL_RADIUS_M;
    requestedRightRadS = (linearMps + angularRadS * wb::WHEEL_SEPARATION_M * 0.5F) /
                         wb::WHEEL_RADIUS_M;
    lastCommandMs = millis();
    statusFlags &= static_cast<uint16_t>(~wb::FLAG_WATCHDOG);
    return true;
  }

  if (strcmp(type, "PING") == 0 && strtok_r(nullptr, ",", &save) == nullptr) {
    char response[32];
    snprintf(response, sizeof(response), "PONG,%u", sequence);
    wb::writeFrame(Serial, response);
    return true;
  }

  if (strcmp(type, "ESTOP") == 0) {
    const char* stateText = strtok_r(nullptr, ",", &save);
    long state = 0;
    if (!wb::parseLongStrict(stateText, 0, 1, state) || strtok_r(nullptr, ",", &save) != nullptr) {
      sendError(sequence, "SCHEMA");
      return false;
    }
    // A hard-stop circuit always dominates and cannot be cleared in software.
    // Zero the target on either transition so release can never replay a
    // pre-stop command; motion requires a fresh CMD after ESTOP,0.
    softEstop = state == 1;
    requestedLeftRadS = 0.0F;
    requestedRightRadS = 0.0F;
    lastCommandMs = 0;
    statusFlags |= wb::FLAG_WATCHDOG;
    return true;
  }

  sendError(sequence, "TYPE");
  return false;
}

void serviceSerial() {
  while (Serial.available() > 0) {
    const char byte = static_cast<char>(Serial.read());
    const bool completedOverflow = byte == '\n' && receiver.overflowed();
    receiver.push(byte);
    if (completedOverflow) {
      markProtocolFault();
      continue;
    }
    if (!receiver.ready()) continue;
    char* body = wb::validateFrame(receiver.data());
    if (body == nullptr || !parseCommand(body)) markProtocolFault();
    receiver.consume();
  }
}

void updateSafety(unsigned long nowMs) {
  const bool hardEstop = digitalRead(wb::HARD_ESTOP_PIN) == wb::HARD_ESTOP_ACTIVE_STATE;
  const bool watchdog = lastCommandMs == 0 || elapsed(nowMs, lastCommandMs, wb::COMMAND_WATCHDOG_MS);
  if (hardEstop) {
    statusFlags |= wb::FLAG_HARD_ESTOP;
    // Latch the software stop too. Releasing the physical contact therefore
    // cannot restart a continuously publishing host; an operator must issue
    // ESTOP,0 and then a new velocity command.
    softEstop = true;
    requestedLeftRadS = 0.0F;
    requestedRightRadS = 0.0F;
    lastCommandMs = 0;
  } else {
    statusFlags &= static_cast<uint16_t>(~wb::FLAG_HARD_ESTOP);
  }
  if (softEstop) statusFlags |= wb::FLAG_SOFT_ESTOP;
  else statusFlags &= static_cast<uint16_t>(~wb::FLAG_SOFT_ESTOP);
  if (watchdog) statusFlags |= wb::FLAG_WATCHDOG;
  else statusFlags &= static_cast<uint16_t>(~wb::FLAG_WATCHDOG);
  if (static_cast<long>(nowMs - protocolFaultUntilMs) >= 0)
    statusFlags &= static_cast<uint16_t>(~wb::FLAG_PROTOCOL_ERROR);
  if (batteryMv > 0 && batteryMv <= wb::BATTERY_WARNING_MV) statusFlags |= wb::FLAG_LOW_BATTERY;
  else statusFlags &= static_cast<uint16_t>(~wb::FLAG_LOW_BATTERY);

  const bool previousLowVoltageStop = lowVoltageMotorStopActive;
  lowVoltageMotorStopActive = wb::ENABLE_LOW_VOLTAGE_MOTOR_STOP &&
      wb::nextLowVoltageMotorStop(lowVoltageMotorStopActive, batteryMv,
                                  wb::BATTERY_STOP_MV,
                                  wb::BATTERY_STOP_HYSTERESIS_MV);
  if (lowVoltageMotorStopActive != previousLowVoltageStop) {
    // Either edge invalidates freshness, so recovery cannot replay a target
    // accepted while voltage-based motion inhibition was active.
    requestedLeftRadS = 0.0F;
    requestedRightRadS = 0.0F;
    lastCommandMs = 0;
    statusFlags |= wb::FLAG_WATCHDOG;
  }
}

bool motionEnabled() {
  const uint16_t blocking = wb::FLAG_WATCHDOG | wb::FLAG_HARD_ESTOP | wb::FLAG_SOFT_ESTOP;
  return (statusFlags & blocking) == 0U && !lowVoltageMotorStopActive;
}

void updateControl(unsigned long nowMs) {
  if (!elapsed(nowMs, lastControlMs, wb::CONTROL_PERIOD_MS)) return;
  const unsigned long deltaMs = nowMs - lastControlMs;
  lastControlMs = nowMs;
  const float dt = static_cast<float>(deltaMs) / 1000.0F;
  int32_t currentLeft = 0;
  int32_t currentRight = 0;
  snapshotTicks(currentLeft, currentRight);
  const float radiansPerTick = 2.0F * PI / static_cast<float>(wb::ENCODER_TICKS_PER_REVOLUTION);
  measuredLeftRadS = static_cast<float>(currentLeft - previousLeftTicks) * radiansPerTick / dt;
  measuredRightRadS = static_cast<float>(currentRight - previousRightTicks) * radiansPerTick / dt;
  previousLeftTicks = currentLeft;
  previousRightTicks = currentRight;

  const bool enabled = motionEnabled();
  if (enabled) {
    rampedLeftRadS = wb::rampTarget(rampedLeftRadS, requestedLeftRadS);
    rampedRightRadS = wb::rampTarget(rampedRightRadS, requestedRightRadS);
  } else {
    rampedLeftRadS = 0.0F;
    rampedRightRadS = 0.0F;
  }
  leftMotor.setTarget(rampedLeftRadS);
  rightMotor.setTarget(rampedRightRadS);
  leftMotor.update(measuredLeftRadS, dt, enabled);
  rightMotor.update(measuredRightRadS, dt, enabled);
}

void sendOdometry(unsigned long nowMs) {
  if (!elapsed(nowMs, lastOdomMs, wb::ODOM_PERIOD_MS)) return;
  lastOdomMs = nowMs;
  int32_t left = 0;
  int32_t right = 0;
  snapshotTicks(left, right);
  char body[112];
  snprintf(body, sizeof(body), "ODOM,%u,%ld,%ld,%ld,%ld,%u,%u",
           static_cast<unsigned int>(telemetrySequence++),
           static_cast<long>(left), static_cast<long>(right),
           static_cast<long>(measuredLeftRadS * 1000.0F),
           static_cast<long>(measuredRightRadS * 1000.0F),
           static_cast<unsigned int>(batteryMv),
           static_cast<unsigned int>(statusFlags));
  wb::writeFrame(Serial, body);
}

bool initializeImu() {
  if (!wb::ENABLE_MPU6050) return false;
  Wire.beginTransmission(wb::MPU6050_ADDRESS);
  Wire.write(0x6B);  // PWR_MGMT_1
  Wire.write(0x00);  // wake; use internal 8 MHz clock until calibrated
  return Wire.endTransmission() == 0;
}

bool readImu(int16_t& axMg, int16_t& ayMg, int16_t& azMg, int32_t& gxMdps,
             int32_t& gyMdps, int32_t& gzMdps) {
  Wire.beginTransmission(wb::MPU6050_ADDRESS);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(wb::MPU6050_ADDRESS, static_cast<uint8_t>(14), static_cast<uint8_t>(true)) != 14)
    return false;
  auto read16 = []() -> int16_t {
    return static_cast<int16_t>((static_cast<uint16_t>(Wire.read()) << 8) | Wire.read());
  };
  const int16_t rawAx = read16();
  const int16_t rawAy = read16();
  const int16_t rawAz = read16();
  (void)read16();  // temperature
  const int16_t rawGx = read16();
  const int16_t rawGy = read16();
  const int16_t rawGz = read16();
  axMg = static_cast<int16_t>(static_cast<int32_t>(rawAx) * 1000L / 16384L);
  ayMg = static_cast<int16_t>(static_cast<int32_t>(rawAy) * 1000L / 16384L);
  azMg = static_cast<int16_t>(static_cast<int32_t>(rawAz) * 1000L / 16384L);
  gxMdps = static_cast<int32_t>(rawGx) * 1000L / 131L;
  gyMdps = static_cast<int32_t>(rawGy) * 1000L / 131L;
  gzMdps = static_cast<int32_t>(rawGz) * 1000L / 131L;
  return true;
}

void sendImu(unsigned long nowMs) {
  if (!elapsed(nowMs, lastImuMs, wb::IMU_PERIOD_MS)) return;
  lastImuMs = nowMs;
  if (!imuAvailable) return;
  int16_t ax = 0, ay = 0, az = 0;
  int32_t gx = 0, gy = 0, gz = 0;
  if (!readImu(ax, ay, az, gx, gy, gz)) {
    statusFlags |= wb::FLAG_IMU_ERROR;
    imuAvailable = false;
    return;
  }
  statusFlags &= static_cast<uint16_t>(~wb::FLAG_IMU_ERROR);
  char body[112];
  snprintf(body, sizeof(body), "IMU,%u,%d,%d,%d,%ld,%ld,%ld",
           static_cast<unsigned int>(telemetrySequence++), ax, ay, az,
           static_cast<long>(gx), static_cast<long>(gy), static_cast<long>(gz));
  wb::writeFrame(Serial, body);
}

void startRangeMeasurement(unsigned long nowUs) {
  digitalWrite(wb::ULTRASONIC_TRIGGER_PIN, HIGH);
  rangePhase = RangePhase::TRIGGER_HIGH;
  rangePhaseStartedUs = nowUs;
}

void serviceRange(unsigned long nowMs, unsigned long nowUs) {
  switch (rangePhase) {
    case RangePhase::IDLE:
      if (elapsed(nowMs, lastRangeMs, wb::RANGE_PERIOD_MS)) {
        lastRangeMs = nowMs;
        startRangeMeasurement(nowUs);
      }
      break;
    case RangePhase::TRIGGER_HIGH:
      if (static_cast<unsigned long>(nowUs - rangePhaseStartedUs) >= 10UL) {
        digitalWrite(wb::ULTRASONIC_TRIGGER_PIN, LOW);
        rangePhase = RangePhase::WAIT_RISE;
        rangePhaseStartedUs = nowUs;
      }
      break;
    case RangePhase::WAIT_RISE:
      if (digitalRead(wb::ULTRASONIC_ECHO_PIN) == HIGH) {
        echoStartedUs = nowUs;
        rangePhase = RangePhase::WAIT_FALL;
      } else if (static_cast<unsigned long>(nowUs - rangePhaseStartedUs) > 12000UL) {
        statusFlags |= wb::FLAG_RANGE_TIMEOUT;
        rangePhase = RangePhase::IDLE;
      }
      break;
    case RangePhase::WAIT_FALL:
      if (digitalRead(wb::ULTRASONIC_ECHO_PIN) == LOW) {
        const unsigned long echoUs = nowUs - echoStartedUs;
        frontRangeMm = static_cast<uint16_t>(constrain(echoUs * 10UL / 58UL, 20UL, 2000UL));
        statusFlags &= static_cast<uint16_t>(~wb::FLAG_RANGE_TIMEOUT);
        char body[48];
        snprintf(body, sizeof(body), "RANGE,%u,%u",
                 static_cast<unsigned int>(telemetrySequence++),
                 static_cast<unsigned int>(frontRangeMm));
        wb::writeFrame(Serial, body);
        rangePhase = RangePhase::IDLE;
      } else if (static_cast<unsigned long>(nowUs - echoStartedUs) > 12000UL) {
        statusFlags |= wb::FLAG_RANGE_TIMEOUT;
        rangePhase = RangePhase::IDLE;
      }
      break;
  }
}

void updateBattery(unsigned long nowMs) {
  if (!elapsed(nowMs, lastBatteryMs, wb::BATTERY_PERIOD_MS)) return;
  lastBatteryMs = nowMs;
  const uint16_t raw = analogRead(wb::BATTERY_SENSE_PIN);
  const float millivolts = static_cast<float>(raw) * wb::ADC_REFERENCE_V *
                           wb::BATTERY_DIVIDER_RATIO * 1000.0F / 1023.0F;
  const uint16_t sample = static_cast<uint16_t>(millivolts);
  batteryMv = batteryMv == 0 ? sample : static_cast<uint16_t>((batteryMv * 3UL + sample) / 4UL);
}

}  // namespace

void setup() {
  pinMode(wb::LEFT_ENCODER_A_PIN, INPUT_PULLUP);
  pinMode(wb::LEFT_ENCODER_B_PIN, INPUT_PULLUP);
  pinMode(wb::RIGHT_ENCODER_A_PIN, INPUT_PULLUP);
  pinMode(wb::RIGHT_ENCODER_B_PIN, INPUT_PULLUP);
  pinMode(wb::HARD_ESTOP_PIN, INPUT_PULLUP);
  pinMode(wb::ULTRASONIC_TRIGGER_PIN, OUTPUT);
  pinMode(wb::ULTRASONIC_ECHO_PIN, INPUT);
  digitalWrite(wb::ULTRASONIC_TRIGGER_PIN, LOW);

  leftMotor.begin();
  rightMotor.begin();
  attachInterrupt(digitalPinToInterrupt(wb::LEFT_ENCODER_A_PIN), leftEncoderIsr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(wb::RIGHT_ENCODER_A_PIN), rightEncoderIsr, CHANGE);

  Serial.begin(wb::SERIAL_BAUD);
  Wire.begin();
  Wire.setClock(400000UL);
  imuAvailable = initializeImu();
  if (!imuAvailable) statusFlags |= wb::FLAG_IMU_ERROR;
  lastControlMs = millis();
  wb::writeFrame(Serial, "BOOT,0,WILDEBEEST_BASE,1");
}

void loop() {
  const unsigned long nowMs = millis();
  const unsigned long nowUs = micros();
  serviceSerial();
  updateBattery(nowMs);
  updateSafety(nowMs);
  updateControl(nowMs);
  serviceRange(nowMs, nowUs);
  sendImu(nowMs);
  sendOdometry(nowMs);
}
