#pragma once

#include <Arduino.h>
#include <math.h>
#include "Config.h"

namespace wb {

class WheelController {
 public:
  WheelController(uint8_t pwmPin, uint8_t in1Pin, uint8_t in2Pin, bool inverted)
      : pwmPin_(pwmPin), in1Pin_(in1Pin), in2Pin_(in2Pin), inverted_(inverted) {}

  void begin() {
    pinMode(pwmPin_, OUTPUT);
    pinMode(in1Pin_, OUTPUT);
    pinMode(in2Pin_, OUTPUT);
    stop();
  }

  void setTarget(float target) { target_ = constrain(target, -MAX_WHEEL_RAD_S, MAX_WHEEL_RAD_S); }
  float target() const { return target_; }
  float measured() const { return measured_; }

  void update(float measured, float dtSeconds, bool enabled) {
    measured_ = measured;
    if (!enabled || fabs(target_) < 0.01F) {
      integral_ = 0.0F;
      previousError_ = 0.0F;
      stop();
      return;
    }

    const float error = target_ - measured_;
    integral_ = constrain(integral_ + error * dtSeconds, -20.0F, 20.0F);
    const float derivative = dtSeconds > 0.0F ? (error - previousError_) / dtSeconds : 0.0F;
    previousError_ = error;
    float command = FEEDFORWARD_PWM_PER_RAD_S * target_ + PID_KP * error +
                    PID_KI * integral_ + PID_KD * derivative;
    command = constrain(command, -static_cast<float>(PWM_MAX), static_cast<float>(PWM_MAX));
    applyPwm(static_cast<int16_t>(command));
  }

  void stop() {
    analogWrite(pwmPin_, 0);
    digitalWrite(in1Pin_, LOW);
    digitalWrite(in2Pin_, LOW);
  }

 private:
  void applyPwm(int16_t signedPwm) {
    if (inverted_) signedPwm = -signedPwm;
    const bool forward = signedPwm >= 0;
    uint8_t magnitude = static_cast<uint8_t>(abs(signedPwm));
    if (magnitude > 0 && magnitude < PWM_DEADBAND) magnitude = PWM_DEADBAND;
    digitalWrite(in1Pin_, forward ? HIGH : LOW);
    digitalWrite(in2Pin_, forward ? LOW : HIGH);
    analogWrite(pwmPin_, magnitude);
  }

  uint8_t pwmPin_;
  uint8_t in1Pin_;
  uint8_t in2Pin_;
  bool inverted_;
  float target_ = 0.0F;
  float measured_ = 0.0F;
  float integral_ = 0.0F;
  float previousError_ = 0.0F;
};

inline float rampTarget(float current, float requested) {
  return current + constrain(requested - current, -MAX_TARGET_STEP_RAD_S, MAX_TARGET_STEP_RAD_S);
}

}  // namespace wb
