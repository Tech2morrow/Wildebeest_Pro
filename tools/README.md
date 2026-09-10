# Host-side tools

- `wildebeest_protocol.py` is the dependency-free reference codec.
- `mock_mcu.py` emulates the Arduino protocol for bridge testing.
- `robot_doctor.py` checks the repository and flags unverified commissioning data.

The reference codec enforces protocol v1's 128-byte complete-frame limit,
`0..20000 mV` battery field, and `0..2000 mm` front-range field.

Examples:

```bash
python3 -m unittest discover -s tools/tests -v
python3 tools/mock_mcu.py --demo --seconds 1
python3 tools/mock_mcu.py --tcp 8765
python3 tools/robot_doctor.py
```

The mock is a protocol and integration aid. It is not a dynamics, timing, or
safety certification model.
