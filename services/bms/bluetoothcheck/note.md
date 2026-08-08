Packet dump: [broadcastUpdate.docx](<https://unimelbcloud.sharepoint.com/:w:/r/sites/MUR/Design%20Archive/2024/All%20Team%20Files/(LV)%20Low%20Voltage/PDM/Misc%20Files/broadcastUpdate.docx?d=wf4584b22f6c0463f9d381c0f9506dbf8&csf=1&web=1&e=fvKRr8>)
decoding: https://codepen.io/hippityyy/pen/gbYpXBM
Sample hook js: [SmartPower_hook.js](https://unimelbcloud-my.sharepoint.com/:u:/g/personal/rrxie_student_unimelb_edu_au/IQCfBxq1nqruQKUop_Ih9BAVAdfOUqh6vySrXobfkctJ69k?e=KRphk0)

logic:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ BLE NOTIFICATIONS ARRIVE                                                     │
│                                                                              │
│ Chunk 1: [F3 45 31 32 33 33 30 30 30 30 44 35 46 41 46 46 46 46 32 30]      │
│ Chunk 2: [34 45 30 30 30 30 30 31 30 30 32 44 30 30 42 34 30 42 30 30]      │
│ Chunk 3: [38 30 30 37 39 34 42 45 30 43 43 34]                               │
│ ...                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ feed() ADDS TO BUFFER                                                        │
│                                                                              │
│ buffer = [F3 45 31 32 33 ... (all chunks combined)]                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ SEARCH FOR HEADER (F3 45)                                                    │
│                                                                              │
│ Found at index 0                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ CHECK END PATTERN AT POSITION 113                                            │
│                                                                              │
│ buffer[113:121] = [03 03 03 03 03 03 03 03]                                  │
│ ✅ Matches!                                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ VERIFY CRC                                                                   │
│                                                                              │
│ payload_bytes = buffer[2:109]                                                │
│ received_crc = buffer[109:113] (big-endian)                                  │
│ calculated_crc = crc32(payload_bytes)                                        │
│                                                                              │
│ ✅ received_crc == calculated_crc                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ EXTRACT PAYLOAD STRING                                                       │
│                                                                              │
│ payload_bytes = [31 32 33 33 30 30 30 30 ...]                                │
│     ↓ decode('ascii')                                                        │
│ payload_str = "12330000D5FAFFFF204E0000..."                                   │
│                                                                              │
│ Return this string!                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ REMOVE PACKET FROM BUFFER                                                    │
│                                                                              │
│ buffer = buffer[121:]  (keep remaining bytes for next packet)                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LOOP: Check if buffer still has ≥121 bytes                                   │
│ If yes → Find next packet                                                    │
│ If no → Wait for more feed() calls                                           │
└─────────────────────────────────────────────────────────────────────────────┘


raw_bytes:
┌──────┬──────────────────────────┬──────────────┬──────────────────────┐
│  F3  │  108 bytes of ASCII hex  │  4 bytes CRC │  8 bytes of 0x03    │
│  0   │        1-108             │   109-112    │      113-120         │
└──────┴──────────────────────────┴──────────────┴──────────────────────┘

checksum & 0xFFFF
    │       │
    │       └── 16-bit mask (1111 1111 1111 1111)
    │
    └── Keep only the lowest 16 bits, discard everything else

TWO BYTES BECOME ONE VALUE:

BLE sends:    [0x32] [0x31]          ← 2 bytes transmitted
                ↓      ↓
ASCII chars:   '2'    '1'           ← 2 characters
                └──┬──┘
Hex string:      "21"               ← 1 hex pair
                  ↓
Decoded value:   0x21 = 33          ← 1 actual data byte

108 bytes transmitted over BLE
    ↓
54 bytes of actual data
```
