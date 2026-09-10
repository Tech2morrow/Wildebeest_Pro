#include <string.h>
#include <unity.h>

#include "BatterySafety.h"
#include "Config.h"
#include "Protocol.h"

namespace {

void pushText(wb::LineReceiver& receiver, const char* text) {
  while (*text != '\0') receiver.push(*text++);
}

void testCrcCheckValue() {
  const char* input = "123456789";
  TEST_ASSERT_EQUAL_HEX16(
      0x29B1U,
      wb::crc16CcittFalse(reinterpret_cast<const uint8_t*>(input), strlen(input)));
}

void testReceiverResynchronizesAtMidFrameStart() {
  wb::LineReceiver receiver;
  pushText(receiver, "noise@BROKEN,1@PING,42*F43D\n");
  TEST_ASSERT_TRUE(receiver.ready());
  TEST_ASSERT_EQUAL_STRING("@PING,42*F43D", receiver.data());
  TEST_ASSERT_EQUAL_STRING("PING,42", wb::validateFrame(receiver.data()));
}

void testReceiverHonors128ByteCapacityAndRecovers() {
  wb::LineReceiver receiver;
  receiver.push('@');
  for (size_t index = 0; index < wb::RX_FRAME_CAPACITY - 1; ++index) {
    receiver.push('X');
  }
  TEST_ASSERT_TRUE(receiver.overflowed());
  pushText(receiver, "@PING,42*F43D\n");
  TEST_ASSERT_TRUE(receiver.ready());
  TEST_ASSERT_EQUAL_STRING("@PING,42*F43D", receiver.data());
}

void testCanonicalIntegerParsing() {
  long value = 0;
  TEST_ASSERT_TRUE(wb::parseLongStrict("-450", -450, 450, value));
  TEST_ASSERT_EQUAL_INT32(-450, value);
  TEST_ASSERT_FALSE(wb::parseLongStrict("+1", -450, 450, value));
  TEST_ASSERT_FALSE(wb::parseLongStrict("01", -450, 450, value));
  TEST_ASSERT_FALSE(wb::parseLongStrict("451", -450, 450, value));
}

void testLowVoltageCutoffUsesStopThresholdAndHysteresis() {
  bool stopped = false;
  stopped = wb::nextLowVoltageMotorStop(
      stopped, wb::BATTERY_STOP_MV, wb::BATTERY_STOP_MV,
      wb::BATTERY_STOP_HYSTERESIS_MV);
  TEST_ASSERT_TRUE(stopped);
  stopped = wb::nextLowVoltageMotorStop(
      stopped, wb::BATTERY_STOP_MV + wb::BATTERY_STOP_HYSTERESIS_MV - 1,
      wb::BATTERY_STOP_MV, wb::BATTERY_STOP_HYSTERESIS_MV);
  TEST_ASSERT_TRUE(stopped);
  stopped = wb::nextLowVoltageMotorStop(
      stopped, wb::BATTERY_STOP_MV + wb::BATTERY_STOP_HYSTERESIS_MV,
      wb::BATTERY_STOP_MV, wb::BATTERY_STOP_HYSTERESIS_MV);
  TEST_ASSERT_FALSE(stopped);
  TEST_ASSERT_FALSE(wb::nextLowVoltageMotorStop(
      stopped, 0U, wb::BATTERY_STOP_MV, wb::BATTERY_STOP_HYSTERESIS_MV));
}

}  // namespace

void setUp() {}
void tearDown() {}

int runTests() {
  UNITY_BEGIN();
  RUN_TEST(testCrcCheckValue);
  RUN_TEST(testReceiverResynchronizesAtMidFrameStart);
  RUN_TEST(testReceiverHonors128ByteCapacityAndRecovers);
  RUN_TEST(testCanonicalIntegerParsing);
  RUN_TEST(testLowVoltageCutoffUsesStopThresholdAndHysteresis);
  return UNITY_END();
}

#ifdef ARDUINO
void setup() {
  delay(2000);
  runTests();
}

void loop() {}
#else
int main(int, char**) { return runTests(); }
#endif
