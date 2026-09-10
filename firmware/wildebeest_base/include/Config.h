#pragma once

#include <Arduino.h>

namespace wb {

// Serial and scheduler -------------------------------------------------------
constexpr unsigned long SERIAL_BAUD = 115200UL;
constexpr uint16_t COMMAND_WATCHDOG_MS = 300;
constexpr uint16_t CONTROL_PERIOD_MS = 20;       // 50 Hz
constexpr uint16_t ODOM_PERIOD_MS = 50;          // 20 Hz
constexpr uint16_t IMU_PERIOD_MS = 20;           // 50 Hz
constexpr uint16_t RANGE_PERIOD_MS = 100;        // 10 Hz
constexpr uint16_t BATTERY_PERIOD_MS = 250;      // 4 Hz

// Four-wheel skid-steer geometry audited from the placed CAD meshes. The two
// motors on each side share a side command. Measure loaded radius and calibrate
// effective separation on the finished robot before autonomous use.
constexpr float WHEEL_RADIUS_M = 0.033622F;
constexpr float WHEEL_SEPARATION_M = 0.121843F;
constexpr int32_t ENCODER_TICKS_PER_REVOLUTION = 600;

// Command limits. A frame outside these limits is rejected, not clamped.
constexpr int16_t MAX_LINEAR_MM_S = 450;
constexpr int16_t MAX_ANGULAR_MRAD_S = 1800;
constexpr float MAX_WHEEL_RAD_S = 18.0F;

// L298N motor driver ---------------------------------------------------------
constexpr uint8_t LEFT_PWM_PIN = 5;
constexpr uint8_t LEFT_IN1_PIN = 7;
constexpr uint8_t LEFT_IN2_PIN = 8;
constexpr uint8_t RIGHT_PWM_PIN = 6;
constexpr uint8_t RIGHT_IN1_PIN = 9;
constexpr uint8_t RIGHT_IN2_PIN = 10;
constexpr bool LEFT_MOTOR_INVERTED = false;
constexpr bool RIGHT_MOTOR_INVERTED = true;
constexpr uint8_t PWM_DEADBAND = 35;
constexpr uint8_t PWM_MAX = 220;  // preserves control headroom and reduces stress

// Encoder inputs. CPR means the effective count produced by this exact ISR mode.
constexpr uint8_t LEFT_ENCODER_A_PIN = 2;
constexpr uint8_t LEFT_ENCODER_B_PIN = 4;
constexpr uint8_t RIGHT_ENCODER_A_PIN = 3;
constexpr uint8_t RIGHT_ENCODER_B_PIN = 12;
constexpr bool LEFT_ENCODER_INVERTED = false;
constexpr bool RIGHT_ENCODER_INVERTED = true;

// Safety and auxiliary IO ----------------------------------------------------
constexpr uint8_t ULTRASONIC_TRIGGER_PIN = 11;
constexpr uint8_t ULTRASONIC_ECHO_PIN = A0;
// Wire A1 through the normally-closed auxiliary contact to GND. Healthy = LOW;
// pressed, unplugged, or broken wire = HIGH via INPUT_PULLUP. The main E-stop
// contact must independently remove motor power; this input is only monitoring.
constexpr uint8_t HARD_ESTOP_PIN = A1;
constexpr uint8_t HARD_ESTOP_ACTIVE_STATE = HIGH;
constexpr uint8_t BATTERY_SENSE_PIN = A2;

// Divider defaults: 100 kOhm high side, 47 kOhm low side. Verify with a meter.
constexpr float ADC_REFERENCE_V = 5.0F;
constexpr float BATTERY_DIVIDER_RATIO = 3.1276596F;
constexpr uint16_t BATTERY_WARNING_MV = 6800;
constexpr uint16_t BATTERY_STOP_MV = 6600;
// When enabled, motion may re-arm at 6750 mV after stopping at 6600 mV.
// The gap avoids rapid enable/disable cycling around the stop threshold.
constexpr uint16_t BATTERY_STOP_HYSTERESIS_MV = 150;
constexpr bool ENABLE_LOW_VOLTAGE_MOTOR_STOP = false;
static_assert(BATTERY_STOP_MV + BATTERY_STOP_HYSTERESIS_MV <= BATTERY_WARNING_MV,
              "battery stop release must remain within the warning region");

// Controller values are safe starting points, not tuned values.
constexpr float PID_KP = 11.0F;
constexpr float PID_KI = 4.0F;
constexpr float PID_KD = 0.08F;
constexpr float FEEDFORWARD_PWM_PER_RAD_S = 10.0F;
constexpr float MAX_TARGET_STEP_RAD_S = 0.8F;  // per 20 ms control step

// MPU-6050 on the Uno I2C bus (A4 SDA / A5 SCL).
constexpr bool ENABLE_MPU6050 = true;
constexpr uint8_t MPU6050_ADDRESS = 0x68;

// Fault/status bits carried in ODOM telemetry.
enum StatusFlag : uint16_t {
  FLAG_WATCHDOG = 1U << 0,
  FLAG_HARD_ESTOP = 1U << 1,
  FLAG_SOFT_ESTOP = 1U << 2,
  FLAG_PROTOCOL_ERROR = 1U << 3,
  FLAG_IMU_ERROR = 1U << 4,
  FLAG_RANGE_TIMEOUT = 1U << 5,
  FLAG_LOW_BATTERY = 1U << 6,
};

}  // namespace wb
