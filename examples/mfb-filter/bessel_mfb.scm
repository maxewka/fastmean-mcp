scm:
  MajorVersion: 5
  MinorVersion: 1
  General:
    Scale: 30
    HPos: 1910
    VPos: 1040
    SWidth: 3800
    SHeight: 3000
  Special:
    LangVersion: 2
  Scheme:
    MajorSchVer: 3
    MinorSchVer: 0
    Objects:
      - ID: 1
        Type: 2010
        Name: VIN
        X: 800
        Y: 1160
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          ST: 2
          DC:
            U0: 1.0
            Delay: 0
            TFR: 1n
          AC:
            U0: VPEAK
            F: 1000.0
            PHI0: -90.0
            FD: 0
            NP: 1
            Delay: 0
          PULSE:
            F: 1000
            K: 50
            UMAX: 1.0
            UMIN: 0
            TFR: 1n
            Delay: 0
          TRIANG:
            F: 1000
            K: 50
            UMAX: 1.0
            UMIN: 0
            Delay: 0
          USER:
            ScaleT: 1
            ScaleU: 1
            OffsetU: 0
            Delay: 0
            PER: 0
            NP: 1
            U:
              x:
                - 0
                - 0.05
                - 0.5
                - 0.55
                - 1
              y:
                - 0
                - 1
                - 1
                - 0
                - 0
      - ID: 2
        Type: 1000
        Name: R1A
        X: 920
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 3
        Type: 1000
        Name: R3A
        X: 1160
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 4
        Type: 6400
        Name: OA1
        X: 1400
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          k: 100000000.0
      - ID: 5
        Type: 1000
        Name: R2A
        X: 1280
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 6
        Type: 1001
        Name: C1A
        X: 1400
        Y: 680
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: CAP1A
          IC: 0.0
      - ID: 7
        Type: 1001
        Name: C2A
        X: 1040
        Y: 1160
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: CAP2A
          IC: 0.0
      - ID: 8
        Type: 1000
        Name: R1B
        X: 1640
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 9
        Type: 1000
        Name: R3B
        X: 1880
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 10
        Type: 6400
        Name: OA2
        X: 2120
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          k: 100000000.0
      - ID: 11
        Type: 1000
        Name: R2B
        X: 2000
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 12
        Type: 1001
        Name: C1B
        X: 2120
        Y: 680
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: CAP1B
          IC: 0.0
      - ID: 13
        Type: 1001
        Name: C2B
        X: 1760
        Y: 1160
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: CAP2B
          IC: 0.0
      - ID: 14
        Type: 1000
        Name: R1C
        X: 2360
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 15
        Type: 1000
        Name: R3C
        X: 2600
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 16
        Type: 6400
        Name: OA3
        X: 2840
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          k: 100000000.0
      - ID: 17
        Type: 1000
        Name: R2C
        X: 2720
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RBASE
      - ID: 18
        Type: 1001
        Name: C1C
        X: 2840
        Y: 680
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: CAP1C
          IC: 0.0
      - ID: 19
        Type: 1001
        Name: C2C
        X: 2480
        Y: 1160
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: CAP2C
          IC: 0.0
      - ID: 20
        Type: 1000
        Name: RL
        X: 2960
        Y: 1160
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: RLOAD
      - ID: 21
        Type: 200
        Name: GND1
        X: 1880
        Y: 1400
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 22
        Type: 400
        Name: IN
        X: 680
        Y: 1000
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 23
        Type: 400
        Name: S1
        X: 1520
        Y: 860
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 24
        Type: 400
        Name: S2
        X: 2240
        Y: 860
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 25
        Type: 400
        Name: OUT
        X: 3080
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 26
        Type: 300
        Name: CON26
        X: 1448
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 27
        Type: 300
        Name: CON27
        X: 1448
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 28
        Type: 300
        Name: CON28
        X: 1448
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 30
        Type: 300
        Name: CON30
        X: 1460
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 32
        Type: 300
        Name: CON32
        X: 2168
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 33
        Type: 300
        Name: CON33
        X: 2168
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 34
        Type: 300
        Name: CON34
        X: 2168
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 36
        Type: 300
        Name: CON36
        X: 2180
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 38
        Type: 300
        Name: CON38
        X: 2888
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 39
        Type: 300
        Name: CON39
        X: 2888
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 41
        Type: 300
        Name: CON41
        X: 2900
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 42
        Type: 300
        Name: CON42
        X: 2960
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 43
        Type: 300
        Name: CON43
        X: 1040
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 45
        Type: 300
        Name: CON45
        X: 1116
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 46
        Type: 300
        Name: CON46
        X: 1760
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 48
        Type: 300
        Name: CON48
        X: 1836
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 49
        Type: 300
        Name: CON49
        X: 2480
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 51
        Type: 300
        Name: CON51
        X: 2556
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 52
        Type: 300
        Name: CON52
        X: 800
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 54
        Type: 300
        Name: CON54
        X: 1248
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 57
        Type: 300
        Name: CON57
        X: 1968
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 60
        Type: 300
        Name: CON60
        X: 2688
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 63
        Type: 300
        Name: CON63
        X: 1040
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 65
        Type: 300
        Name: CON65
        X: 1340
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 67
        Type: 300
        Name: CON67
        X: 1376
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 68
        Type: 300
        Name: CON68
        X: 1760
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 69
        Type: 300
        Name: CON69
        X: 1880
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 71
        Type: 300
        Name: CON71
        X: 2060
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 73
        Type: 300
        Name: CON73
        X: 2096
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 74
        Type: 300
        Name: CON74
        X: 2480
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 76
        Type: 300
        Name: CON76
        X: 2780
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 78
        Type: 300
        Name: CON78
        X: 2816
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 79
        Type: 900
        Name: MCP_NOTE_79
        X: 680
        Y: 1520
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: ".parameter\r\nVPEAK=1 \"VPEAK [V]\";\r\nRBASE=10000 \"RBASE [ohm]\";\r\nRLOAD=10000 \"RLOAD [ohm]\";\r\n\
            CAP1A=6.4733303044821449e-09 \"CAP1A [F]\";\r\nCAP2A=1.5171251704818343e-08 \"CAP2A [F]\";\r\nCAP1B=5.1320973102588036e-09\
            \ \"CAP1B [F]\";\r\nCAP2B=1.7254567708466816e-08 \"CAP2B [F]\";\r\nCAP1C=2.7181911749820821e-09 \"CAP1C [F]\"\
            ;\r\n"
          Color: 00808000
          Font:
            lfHeight: -16
            lfWidth: 0
            lfEscapement: 0
            lfOrientation: 0
            lfWeight: 0
            lfItalic: 0
            lfUnderline: 0
            lfStrikeOut: 0
            lfCharSet: 204
            lfOutPrecision: 0
            lfClipPrecision: 0
            lfQuality: 0
            lfPitchAndFamily: 0
            lfFaceName: Courier New
      - ID: 80
        Type: 900
        Name: MCP_NOTE_80
        X: 680
        Y: 1753
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: ".parameter\r\nCAP2C=2.5622018052579155e-08 \"CAP2C [F]\";\r\n"
          Color: 00808000
          Font:
            lfHeight: -16
            lfWidth: 0
            lfEscapement: 0
            lfOrientation: 0
            lfWeight: 0
            lfItalic: 0
            lfUnderline: 0
            lfStrikeOut: 0
            lfCharSet: 204
            lfOutPrecision: 0
            lfClipPrecision: 0
            lfQuality: 0
            lfPitchAndFamily: 0
            lfFaceName: Courier New
      - ID: 81
        Type: 900
        Name: MCP_NOTE_81
        X: 680
        Y: 1832
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Bessel MFB: 3 cascaded second-order stages; corner about 1 kHz.\r\nTI SLOA049D Fig.B-2 topology: 18 parts\
            \ + VIN and RL test fixtures."
          Color: 00808000
          Font:
            lfHeight: -16
            lfWidth: 0
            lfEscapement: 0
            lfOrientation: 0
            lfWeight: 0
            lfItalic: 0
            lfUnderline: 0
            lfStrikeOut: 0
            lfCharSet: 204
            lfOutPrecision: 0
            lfClipPrecision: 0
            lfQuality: 0
            lfPitchAndFamily: 0
            lfFaceName: Courier New
      - ID: 82
        Type: 900
        Name: MCP_NOTE_82
        X: 680
        Y: 1911
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "U(IN), U(S1), U(S2), U(OUT): input and stage-output waveforms [V].\r\ndb(U(OUT)/U(IN)): overall gain [dB];\
            \ phs(...): phase [degrees]."
          Color: 00808000
          Font:
            lfHeight: -16
            lfWidth: 0
            lfEscapement: 0
            lfOrientation: 0
            lfWeight: 0
            lfItalic: 0
            lfUnderline: 0
            lfStrikeOut: 0
            lfCharSet: 204
            lfOutPrecision: 0
            lfClipPrecision: 0
            lfQuality: 0
            lfPitchAndFamily: 0
            lfFaceName: Courier New
      - ID: 83
        Type: 900
        Name: MCP_NOTE_83
        X: 680
        Y: 1990
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "db(U(S1)/U(IN)), db(U(S2)/U(IN)): accumulated stage gains [dB].\r\nRBASE changes all nine filter resistors;\
            \ CAP1A through CAP2C set pole pairs."
          Color: 00808000
          Font:
            lfHeight: -16
            lfWidth: 0
            lfEscapement: 0
            lfOrientation: 0
            lfWeight: 0
            lfItalic: 0
            lfUnderline: 0
            lfStrikeOut: 0
            lfCharSet: 204
            lfOutPrecision: 0
            lfClipPrecision: 0
            lfQuality: 0
            lfPitchAndFamily: 0
            lfFaceName: Courier New
      - ID: 84
        Type: 900
        Name: MCP_NOTE_84
        X: 680
        Y: 2069
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Assigned values: RBASE=10 kohm, VIN=1 V peak at 1 kHz, RLOAD=10 kohm.\r\nOA1 through OA3: native ideal gain\
            \ 1e8; no rails, clipping, GBW or current limit."
          Color: 00808000
          Font:
            lfHeight: -16
            lfWidth: 0
            lfEscapement: 0
            lfOrientation: 0
            lfWeight: 0
            lfItalic: 0
            lfUnderline: 0
            lfStrikeOut: 0
            lfCharSet: 204
            lfOutPrecision: 0
            lfClipPrecision: 0
            lfQuality: 0
            lfPitchAndFamily: 0
            lfFaceName: Courier New
    Wires:
      - obj1:
          ID: 5
          pin: 2
        obj2:
          ID: 26
          pin: 1
      - obj1:
          ID: 4
          pin: 3
        obj2:
          ID: 28
          pin: 1
      - obj1:
          ID: 6
          pin: 2
        obj2:
          ID: 30
          pin: 2
      - obj1:
          ID: 26
          pin: 4
        obj2:
          ID: 27
          pin: 2
      - obj1:
          ID: 26
          pin: 3
        obj2:
          ID: 30
          pin: 1
      - obj1:
          ID: 27
          pin: 4
        obj2:
          ID: 28
          pin: 2
      - obj1:
          ID: 27
          pin: 3
        obj2:
          ID: 23
          pin: 1
      - obj1:
          ID: 28
          pin: 3
        obj2:
          ID: 8
          pin: 1
      - obj1:
          ID: 11
          pin: 2
        obj2:
          ID: 32
          pin: 1
      - obj1:
          ID: 10
          pin: 3
        obj2:
          ID: 34
          pin: 1
      - obj1:
          ID: 12
          pin: 2
        obj2:
          ID: 36
          pin: 2
      - obj1:
          ID: 32
          pin: 4
        obj2:
          ID: 33
          pin: 2
      - obj1:
          ID: 32
          pin: 3
        obj2:
          ID: 36
          pin: 1
      - obj1:
          ID: 33
          pin: 4
        obj2:
          ID: 34
          pin: 2
      - obj1:
          ID: 33
          pin: 3
        obj2:
          ID: 24
          pin: 1
      - obj1:
          ID: 34
          pin: 3
        obj2:
          ID: 14
          pin: 1
      - obj1:
          ID: 17
          pin: 2
        obj2:
          ID: 38
          pin: 1
      - obj1:
          ID: 16
          pin: 3
        obj2:
          ID: 39
          pin: 1
      - obj1:
          ID: 18
          pin: 2
        obj2:
          ID: 41
          pin: 2
      - obj1:
          ID: 38
          pin: 4
        obj2:
          ID: 39
          pin: 2
      - obj1:
          ID: 38
          pin: 3
        obj2:
          ID: 41
          pin: 1
      - obj1:
          ID: 39
          pin: 3
        obj2:
          ID: 42
          pin: 1
      - obj1:
          ID: 42
          pin: 4
        obj2:
          ID: 20
          pin: 1
      - obj1:
          ID: 42
          pin: 3
        obj2:
          ID: 25
          pin: 1
      - obj1:
          ID: 2
          pin: 2
        obj2:
          ID: 43
          pin: 1
      - obj1:
          ID: 43
          pin: 4
        obj2:
          ID: 7
          pin: 1
      - obj1:
          ID: 43
          pin: 3
        obj2:
          ID: 45
          pin: 1
      - obj1:
          ID: 45
          pin: 2
        obj2:
          ID: 5
          pin: 1
      - obj1:
          ID: 45
          pin: 3
        obj2:
          ID: 3
          pin: 1
      - obj1:
          ID: 8
          pin: 2
        obj2:
          ID: 46
          pin: 1
      - obj1:
          ID: 46
          pin: 4
        obj2:
          ID: 13
          pin: 1
      - obj1:
          ID: 46
          pin: 3
        obj2:
          ID: 48
          pin: 1
      - obj1:
          ID: 48
          pin: 2
        obj2:
          ID: 11
          pin: 1
      - obj1:
          ID: 48
          pin: 3
        obj2:
          ID: 9
          pin: 1
      - obj1:
          ID: 14
          pin: 2
        obj2:
          ID: 49
          pin: 1
      - obj1:
          ID: 49
          pin: 4
        obj2:
          ID: 19
          pin: 1
      - obj1:
          ID: 49
          pin: 3
        obj2:
          ID: 51
          pin: 1
      - obj1:
          ID: 51
          pin: 2
        obj2:
          ID: 17
          pin: 1
      - obj1:
          ID: 51
          pin: 3
        obj2:
          ID: 15
          pin: 1
      - obj1:
          ID: 22
          pin: 1
        obj2:
          ID: 52
          pin: 1
      - obj1:
          ID: 52
          pin: 4
        obj2:
          ID: 1
          pin: 2
      - obj1:
          ID: 52
          pin: 3
        obj2:
          ID: 2
          pin: 1
      - obj1:
          ID: 3
          pin: 2
        obj2:
          ID: 54
          pin: 1
      - obj1:
          ID: 54
          pin: 2
        obj2:
          ID: 6
          pin: 1
      - obj1:
          ID: 54
          pin: 4
        obj2:
          ID: 4
          pin: 2
      - obj1:
          ID: 9
          pin: 2
        obj2:
          ID: 57
          pin: 1
      - obj1:
          ID: 57
          pin: 2
        obj2:
          ID: 12
          pin: 1
      - obj1:
          ID: 57
          pin: 4
        obj2:
          ID: 10
          pin: 2
      - obj1:
          ID: 15
          pin: 2
        obj2:
          ID: 60
          pin: 1
      - obj1:
          ID: 60
          pin: 2
        obj2:
          ID: 18
          pin: 1
      - obj1:
          ID: 60
          pin: 4
        obj2:
          ID: 16
          pin: 2
      - obj1:
          ID: 1
          pin: 1
        obj2:
          ID: 63
          pin: 1
      - obj1:
          ID: 7
          pin: 2
        obj2:
          ID: 63
          pin: 2
      - obj1:
          ID: 63
          pin: 3
        obj2:
          ID: 67
          pin: 1
      - obj1:
          ID: 65
          pin: 2
        obj2:
          ID: 4
          pin: 1
      - obj1:
          ID: 65
          pin: 3
        obj2:
          ID: 67
          pin: 2
      - obj1:
          ID: 67
          pin: 3
        obj2:
          ID: 68
          pin: 1
      - obj1:
          ID: 13
          pin: 2
        obj2:
          ID: 68
          pin: 2
      - obj1:
          ID: 68
          pin: 3
        obj2:
          ID: 69
          pin: 1
      - obj1:
          ID: 69
          pin: 4
        obj2:
          ID: 21
          pin: 1
      - obj1:
          ID: 69
          pin: 3
        obj2:
          ID: 73
          pin: 1
      - obj1:
          ID: 71
          pin: 2
        obj2:
          ID: 10
          pin: 1
      - obj1:
          ID: 71
          pin: 3
        obj2:
          ID: 73
          pin: 2
      - obj1:
          ID: 73
          pin: 3
        obj2:
          ID: 74
          pin: 1
      - obj1:
          ID: 19
          pin: 2
        obj2:
          ID: 74
          pin: 2
      - obj1:
          ID: 74
          pin: 3
        obj2:
          ID: 78
          pin: 1
      - obj1:
          ID: 76
          pin: 2
        obj2:
          ID: 16
          pin: 1
      - obj1:
          ID: 76
          pin: 3
        obj2:
          ID: 78
          pin: 2
      - obj1:
          ID: 78
          pin: 3
        obj2:
          ID: 20
          pin: 2
  TD:
    Expressions:
      - plot: 1
        x: t
        y: U(IN)
      - plot: 2
        x: t
        y: U(S1)
      - plot: 3
        x: t
        y: U(S2)
      - plot: 4
        x: t
        y: U(OUT)
    ExprRowOffset: 0
    IPNum: 1
    IP:
      - StartTime: 0
        EndTime: 0.01
        TimeStep: 2.0e-06
        NumPts: 100
        PtsStepFl: 2
        EPS: 0.001
        GraphType: 1
    IC: 0
    SVD:
      IC: 0
      ICReadFileName: data.sv
      SVWriteFlag: 0
      SVWriteFileName: data.sv
      SV2SchemeFlag: 0
      SVPredictFlag: 0
    ParamSweep: 0
    PSD:
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 1
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
    FFT: 0
    FFTD:
      StartVal: -1
      EndVal: -1
      PointNum: 100
      GraphType: 3
      ShowPointNum: 100
      window_type: 0
  FD:
    StartFreq: 10.0
    EndFreq: 100000.0
    NumPts: 301
    ScaleX: 2
    ScaleY: 1
    AvailScaleX: 3
    AvailScaleY: 3
    Expressions:
      - plot: 1
        x: f
        y: db(U(S1)/U(IN))
      - plot: 2
        x: f
        y: db(U(S2)/U(IN))
      - plot: 3
        x: f
        y: db(U(OUT)/U(IN))
      - plot: 4
        x: f
        y: phs(U(OUT)/U(IN))
    ExprRowOffset: 0
    ParamSweep: 0
    PSD:
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 1
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
      - Component: ''
        ParamIndex: 0
        StartVal: 0
        EndVal: 0
        NumPts: 10
        SweepType: 1
        'On': 0
    FFT: 0
    FFTD:
      StartVal: -1
      EndVal: -1
      PointNum: 100
      GraphType: 3
      ShowPointNum: 100
      window_type: 0
  AOD:
    DrawGraph: 1
    AvailMemory: 536870912
    ShowTransStat: 0
  SOD:
    ShowID: 1
    ShowParam: 1
    ShowNodes: 0
    FontID:
      lfHeight: 100
      lfWidth: 0
      lfEscapement: 0
      lfOrientation: 0
      lfWeight: 400
      lfItalic: 0
      lfUnderline: 0
      lfStrikeOut: 0
      lfCharSet: 1
      lfOutPrecision: 0
      lfClipPrecision: 0
      lfQuality: 0
      lfPitchAndFamily: 0
      lfFaceName: Times New Roman
    FontParam:
      lfHeight: 100
      lfWidth: 0
      lfEscapement: 0
      lfOrientation: 0
      lfWeight: 400
      lfItalic: 0
      lfUnderline: 0
      lfStrikeOut: 0
      lfCharSet: 1
      lfOutPrecision: 0
      lfClipPrecision: 0
      lfQuality: 0
      lfPitchAndFamily: 0
      lfFaceName: Arial
    FontNodes:
      lfHeight: 120
      lfWidth: 0
      lfEscapement: 0
      lfOrientation: 0
      lfWeight: 400
      lfItalic: 0
      lfUnderline: 0
      lfStrikeOut: 0
      lfCharSet: 1
      lfOutPrecision: 0
      lfClipPrecision: 0
      lfQuality: 0
      lfPitchAndFamily: 0
      lfFaceName: Arial
    ColorID: 00FF0000
    ColorParam: 00FF0000
    ColorNodes: 00008000
    Uh: 5
    Ul: 0
    Uh2l: 2.5
    Ul2h: 2.5
  DCOP:
    CountNV: 1
    CountSV: 0
    CountUR: 0
    CountIR: 0
    CountUI: 0
    CountIU: 0
    Digit: 4
