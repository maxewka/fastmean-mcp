scm:
  MajorVersion: 5
  MinorVersion: 1
  General:
    Scale: 100
    HPos: 1340
    VPos: 1320
    SWidth: 3140
    SHeight: 3570
  Special:
    LangVersion: 2
  Scheme:
    MajorSchVer: 3
    MinorSchVer: 0
    Objects:
      - ID: 1
        Type: 2010
        Name: VCC
        X: 240
        Y: 520
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          ST: 1
          DC:
            U0: Vrail
            Delay: 0
            TFR: 1n
          AC:
            U0: 38.0
            F: 1000
            PHI0: 0
            FD: 0
            NP: 1
            Delay: 0
          PULSE:
            F: 1000
            K: 50
            UMAX: 38.0
            UMIN: 0
            TFR: 1n
            Delay: 0
          TRIANG:
            F: 1000
            K: 50
            UMAX: 38.0
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
        Type: 2010
        Name: VEE
        X: 240
        Y: 1800
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          ST: 1
          DC:
            U0: Vrail
            Delay: 0
            TFR: 1n
          AC:
            U0: 38.0
            F: 1000
            PHI0: 0
            FD: 0
            NP: 1
            Delay: 0
          PULSE:
            F: 1000
            K: 50
            UMAX: 38.0
            UMIN: 0
            TFR: 1n
            Delay: 0
          TRIANG:
            F: 1000
            K: 50
            UMAX: 38.0
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
      - ID: 3
        Type: 2010
        Name: VIN
        X: 240
        Y: 1160
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          ST: 2
          DC:
            U0: 1.4142135623730951
            Delay: 0
            TFR: 1n
          AC:
            U0: VinPeak
            F: 1000.0
            PHI0: -90.0
            FD: 0
            NP: 1
            Delay: 0
          PULSE:
            F: 1000
            K: 50
            UMAX: 1.4142135623730951
            UMIN: 0
            TFR: 1n
            Delay: 0
          TRIANG:
            F: 1000
            K: 50
            UMAX: 1.4142135623730951
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
      - ID: 4
        Type: 1000
        Name: RA_P
        X: 1580
        Y: 500
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 8.2
      - ID: 5
        Type: 1000
        Name: RB_P
        X: 1580
        Y: 740
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 4.7
      - ID: 6
        Type: 1001
        Name: CBOOT_P
        X: 1800
        Y: 620
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: Cbootstrap
          IC: 14.29290152254828
      - ID: 7
        Type: 1001
        Name: CIN_P
        X: 600
        Y: 1440
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: Cinput
          IC: -37.025092550958206
      - ID: 8
        Type: 1000
        Name: RIN_P
        X: 900
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 24.0
      - ID: 9
        Type: 1000
        Name: RFB_P
        X: 1040
        Y: 1920
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: Rfeedback
      - ID: 10
        Type: 1000
        Name: RBIAS_P
        X: 980
        Y: 1580
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: Rbias
      - ID: 11
        Type: 1000
        Name: RREF_P
        X: 580
        Y: 1280
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 1000.0
      - ID: 12
        Type: 1101
        Name: DREF_P1
        X: 760
        Y: 1520
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 13
        Type: 1101
        Name: DREF_P2
        X: 760
        Y: 1640
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 14
        Type: 1101
        Name: DREF_P3
        X: 760
        Y: 1760
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 15
        Type: 1101
        Name: DREF_P4
        X: 760
        Y: 1880
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 16
        Type: 1000
        Name: RA_N
        X: 1580
        Y: 1820
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 8.2
      - ID: 17
        Type: 1000
        Name: RB_N
        X: 1580
        Y: 1580
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 4.7
      - ID: 18
        Type: 1001
        Name: CBOOT_N
        X: 1800
        Y: 1700
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: Cbootstrap
          IC: -14.292901522548233
      - ID: 19
        Type: 1001
        Name: CIN_N
        X: 600
        Y: 880
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: Cinput
          IC: 37.02509255095821
      - ID: 20
        Type: 1000
        Name: RIN_N
        X: 900
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 24.0
      - ID: 21
        Type: 1000
        Name: RFB_N
        X: 1040
        Y: 400
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: Rfeedback
      - ID: 22
        Type: 1000
        Name: RBIAS_N
        X: 980
        Y: 740
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: Rbias
      - ID: 23
        Type: 1000
        Name: RREF_N
        X: 580
        Y: 1040
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 1000.0
      - ID: 24
        Type: 1101
        Name: DREF_N1
        X: 760
        Y: 440
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 25
        Type: 1101
        Name: DREF_N2
        X: 760
        Y: 560
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 26
        Type: 1101
        Name: DREF_N3
        X: 760
        Y: 680
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 27
        Type: 1101
        Name: DREF_N4
        X: 760
        Y: 800
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 28
        Type: 1000
        Name: RE_N
        X: 1880
        Y: 1080
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 0.02
      - ID: 29
        Type: 1000
        Name: RE_P
        X: 1880
        Y: 1240
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 0.02
      - ID: 30
        Type: 1000
        Name: RL
        X: 2200
        Y: 1320
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: Rload
      - ID: 31
        Type: 1101
        Name: DCLAMP_N
        X: 1740
        Y: 1040
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 32
        Type: 1101
        Name: DCLAMP_P
        X: 1740
        Y: 1280
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.01
          Roff: 1000000000.0
          Uon: 0.65
      - ID: 33
        Type: 7100
        Name: Q1
        X: 1160
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          FileName: models/NDRV.scm
          Pins:
            Left:
              - B
            Top:
              - C
            Right: []
            Bottom:
              - E
      - ID: 34
        Type: 7100
        Name: Q2
        X: 1160
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          FileName: models/PDRV.scm
          Pins:
            Left:
              - B
            Top:
              - E
            Right: []
            Bottom:
              - C
      - ID: 35
        Type: 7100
        Name: Q3
        X: 1880
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          FileName: models/NOUT.scm
          Pins:
            Left:
              - B
            Top:
              - C
            Right: []
            Bottom:
              - E
      - ID: 36
        Type: 7100
        Name: Q4
        X: 1880
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          FileName: models/POUT.scm
          Pins:
            Left:
              - B
            Top:
              - E
            Right: []
            Bottom:
              - C
      - ID: 37
        Type: 200
        Name: GND1
        X: 240
        Y: 2320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 38
        Type: 400
        Name: IN
        X: 440
        Y: 1160
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 39
        Type: 400
        Name: OUT
        X: 2400
        Y: 1160
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 40
        Type: 400
        Name: VPP
        X: 2400
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 41
        Type: 400
        Name: VNN
        X: 2400
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 43
        Type: 300
        Name: CON43
        X: 460
        Y: 1160
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 44
        Type: 300
        Name: CON44
        X: 460
        Y: 1100
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 47
        Type: 300
        Name: CON47
        X: 980
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 48
        Type: 300
        Name: CON48
        X: 980
        Y: 1520
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 50
        Type: 300
        Name: CON50
        X: 940
        Y: 1520
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 51
        Type: 300
        Name: CON51
        X: 2120
        Y: 1160
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 52
        Type: 300
        Name: CON52
        X: 1100
        Y: 400
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 53
        Type: 300
        Name: CON53
        X: 1860
        Y: 400
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 55
        Type: 300
        Name: CON55
        X: 2120
        Y: 1140
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 57
        Type: 300
        Name: CON57
        X: 1100
        Y: 1500
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 59
        Type: 300
        Name: CON59
        X: 1060
        Y: 740
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 63
        Type: 300
        Name: CON63
        X: 2120
        Y: 1260
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 64
        Type: 300
        Name: CON64
        X: 1880
        Y: 1140
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 66
        Type: 300
        Name: CON66
        X: 980
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 67
        Type: 300
        Name: CON67
        X: 980
        Y: 800
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 69
        Type: 300
        Name: CON69
        X: 940
        Y: 800
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 70
        Type: 300
        Name: CON70
        X: 1580
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 72
        Type: 300
        Name: CON72
        X: 1580
        Y: 960
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 73
        Type: 300
        Name: CON73
        X: 1580
        Y: 1280
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 74
        Type: 300
        Name: CON74
        X: 1580
        Y: 1700
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 75
        Type: 300
        Name: CON75
        X: 1580
        Y: 620
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 77
        Type: 300
        Name: CON77
        X: 1140
        Y: 1360
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 79
        Type: 300
        Name: CON79
        X: 1580
        Y: 940
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 81
        Type: 300
        Name: CON81
        X: 1680
        Y: 940
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 83
        Type: 300
        Name: CON83
        X: 1880
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 85
        Type: 300
        Name: CON85
        X: 1800
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 86
        Type: 300
        Name: CON86
        X: 1880
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 88
        Type: 300
        Name: CON88
        X: 1800
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 89
        Type: 300
        Name: CON89
        X: 760
        Y: 1460
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 92
        Type: 300
        Name: CON92
        X: 780
        Y: 1640
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 94
        Type: 300
        Name: CON94
        X: 760
        Y: 860
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 97
        Type: 300
        Name: CON97
        X: 780
        Y: 680
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 99
        Type: 300
        Name: CON99
        X: 1880
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 101
        Type: 300
        Name: CON101
        X: 760
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 102
        Type: 300
        Name: CON102
        X: 1160
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 103
        Type: 300
        Name: CON103
        X: 1580
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 104
        Type: 300
        Name: CON104
        X: 1880
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 106
        Type: 300
        Name: CON106
        X: 760
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 107
        Type: 300
        Name: CON107
        X: 1160
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 108
        Type: 300
        Name: CON108
        X: 1160
        Y: 440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 110
        Type: 300
        Name: CON110
        X: 240
        Y: 2240
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 112
        Type: 300
        Name: CON112
        X: 200
        Y: 580
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 113
        Type: 300
        Name: CON113
        X: 200
        Y: 1040
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 114
        Type: 300
        Name: CON114
        X: 200
        Y: 1220
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 115
        Type: 300
        Name: CON115
        X: 200
        Y: 1740
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 119
        Type: 300
        Name: CON119
        X: 520
        Y: 1040
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 122
        Type: 300
        Name: CON122
        X: 2420
        Y: 1380
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 123
        Type: 900
        Name: MCP_NOTE_123
        X: 200
        Y: 2440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: ".parameter\r\nRload=1.25 \"Rload [ohm]\";\r\nRfeedback=2958.192887903313 \"Rfeedback [ohm]\";\r\nCinput=0.001\
            \ \"Cinput [F]\";\r\nCbootstrap=0.01 \"Cbootstrap [F]\";\r\nRbias=69.04195248892718 \"Rbias [ohm]\";\r\nVrail=38\
            \ \"Vrail [V]\";\r\nVinPeak=1.4142135623730951 \"VinPeak [V]\";\r\n"
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
      - ID: 124
        Type: 900
        Name: MCP_NOTE_124
        X: 200
        Y: 2651
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "ТЕСТОВЫЙ УСИЛИТЕЛЬ: 4 BJT, синус 1 кГц.\r\nВход 1 В RMS; расчётная нагрузка 1,25 Ом. Питание +/-38 В."
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
      - ID: 125
        Type: 900
        Name: MCP_NOTE_125
        X: 200
        Y: 2730
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Транзисторы: Q1=MJL4281A, Q2=MJL4302A;\r\nQ3=2N5686, Q4=2N5684. Внутри — приближённые PWL-подсхемы."
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
      - ID: 126
        Type: 900
        Name: MCP_NOTE_126
        X: 200
        Y: 2809
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Графики U(IN), U(OUT): входное и выходное напряжения.\r\nУсилитель инвертирующий; модуль усиления около25."
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
      - ID: 127
        Type: 900
        Name: MCP_NOTE_127
        X: 200
        Y: 2888
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "I(RL) — ток нагрузки. При25 В RMS и Rload=1,25 Ом:\r\nIrms=Vrms/Rload=20 А; Pavg=Vrms^2/Rload=500 Вт."
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
      - ID: 128
        Type: 900
        Name: MCP_NOTE_128
        X: 200
        Y: 2967
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "U(OUT)*I(RL) — мгновенная мощность нагрузки.\r\nСреднее за целое число периодов даёт выходную мощность."
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
      - ID: 129
        Type: 900
        Name: MCP_NOTE_129
        X: 200
        Y: 3046
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "I(VIN) — ток входного источника.\r\nНоминально66,8 мА RMS, пик94,5 мА. VinPeak — амплитуда, не RMS."
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
      - ID: 130
        Type: 900
        Name: MCP_NOTE_130
        X: 200
        Y: 3125
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Нелинейная схема: используйте расчёт переходного процесса (TD).\r\nОбычный FD здесь не подтверждён; его графики\
            \ очищены.\r\nДля частотной характеристики нужны отдельные синусные TD-расчёты."
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
      - ID: 131
        Type: 900
        Name: MCP_NOTE_131
        X: 200
        Y: 3226
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Параметры: Rload — нагрузка; Rfeedback — обе цепи ОС;\r\nCinput/Cbootstrap — парные ёмкости; Rbias — настройка\
            \ смещения."
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
      - ID: 132
        Type: 900
        Name: MCP_NOTE_132
        X: 200
        Y: 3305
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Проверено FASTMEAN: около25,003 В RMS,500,10 Вт.\r\nИзмерять после0,25 с; начальный переходный процесс не\
            \ учитывать."
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
      - ID: 133
        Type: 900
        Name: MCP_NOTE_133
        X: 200
        Y: 3384
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "ВАЖНО: учебная номинальная PWL-модель, не проект для сборки.\r\nНет тепловой обратной связи, пробоя, SOA\
            \ и высокочастотных эффектов.\r\nРазброс beta резко меняет ток покоя; нужны перерасчёт и защита."
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
          ID: 44
          pin: 1
        obj2:
          ID: 3
          pin: 2
      - obj1:
          ID: 38
          pin: 1
        obj2:
          ID: 43
          pin: 1
      - obj1:
          ID: 43
          pin: 4
        obj2:
          ID: 7
          pin: 2
      - obj1:
          ID: 43
          pin: 2
        obj2:
          ID: 44
          pin: 4
      - obj1:
          ID: 44
          pin: 2
        obj2:
          ID: 19
          pin: 2
      - obj1:
          ID: 7
          pin: 1
        obj2:
          ID: 8
          pin: 1
      - obj1:
          ID: 8
          pin: 2
        obj2:
          ID: 47
          pin: 1
      - obj1:
          ID: 47
          pin: 3
        obj2:
          ID: 33
          pin: 1
      - obj1:
          ID: 47
          pin: 4
        obj2:
          ID: 48
          pin: 2
      - obj1:
          ID: 10
          pin: 2
        obj2:
          ID: 48
          pin: 4
      - obj1:
          ID: 48
          pin: 1
        obj2:
          ID: 50
          pin: 3
      - obj1:
          ID: 9
          pin: 2
        obj2:
          ID: 50
          pin: 4
      - obj1:
          ID: 51
          pin: 3
        obj2:
          ID: 39
          pin: 1
      - obj1:
          ID: 51
          pin: 2
        obj2:
          ID: 55
          pin: 4
      - obj1:
          ID: 51
          pin: 4
        obj2:
          ID: 63
          pin: 2
      - obj1:
          ID: 21
          pin: 1
        obj2:
          ID: 52
          pin: 1
      - obj1:
          ID: 52
          pin: 3
        obj2:
          ID: 53
          pin: 1
      - obj1:
          ID: 52
          pin: 4
        obj2:
          ID: 59
          pin: 3
      - obj1:
          ID: 53
          pin: 3
        obj2:
          ID: 55
          pin: 2
      - obj1:
          ID: 53
          pin: 4
        obj2:
          ID: 6
          pin: 2
      - obj1:
          ID: 55
          pin: 1
        obj2:
          ID: 64
          pin: 3
      - obj1:
          ID: 9
          pin: 1
        obj2:
          ID: 57
          pin: 4
      - obj1:
          ID: 57
          pin: 1
        obj2:
          ID: 59
          pin: 4
      - obj1:
          ID: 18
          pin: 2
        obj2:
          ID: 63
          pin: 4
      - obj1:
          ID: 63
          pin: 3
        obj2:
          ID: 30
          pin: 1
      - obj1:
          ID: 28
          pin: 2
        obj2:
          ID: 64
          pin: 2
      - obj1:
          ID: 64
          pin: 4
        obj2:
          ID: 29
          pin: 2
      - obj1:
          ID: 20
          pin: 2
        obj2:
          ID: 66
          pin: 1
      - obj1:
          ID: 66
          pin: 3
        obj2:
          ID: 34
          pin: 1
      - obj1:
          ID: 66
          pin: 2
        obj2:
          ID: 67
          pin: 4
      - obj1:
          ID: 22
          pin: 2
        obj2:
          ID: 67
          pin: 2
      - obj1:
          ID: 67
          pin: 1
        obj2:
          ID: 69
          pin: 3
      - obj1:
          ID: 21
          pin: 2
        obj2:
          ID: 69
          pin: 2
      - obj1:
          ID: 70
          pin: 2
        obj2:
          ID: 73
          pin: 4
      - obj1:
          ID: 70
          pin: 4
        obj2:
          ID: 17
          pin: 2
      - obj1:
          ID: 70
          pin: 3
        obj2:
          ID: 36
          pin: 1
      - obj1:
          ID: 34
          pin: 3
        obj2:
          ID: 72
          pin: 1
      - obj1:
          ID: 72
          pin: 4
        obj2:
          ID: 73
          pin: 2
      - obj1:
          ID: 73
          pin: 3
        obj2:
          ID: 32
          pin: 1
      - obj1:
          ID: 74
          pin: 2
        obj2:
          ID: 17
          pin: 1
      - obj1:
          ID: 74
          pin: 4
        obj2:
          ID: 16
          pin: 2
      - obj1:
          ID: 74
          pin: 3
        obj2:
          ID: 18
          pin: 1
      - obj1:
          ID: 75
          pin: 2
        obj2:
          ID: 4
          pin: 2
      - obj1:
          ID: 75
          pin: 4
        obj2:
          ID: 5
          pin: 1
      - obj1:
          ID: 75
          pin: 3
        obj2:
          ID: 6
          pin: 1
      - obj1:
          ID: 33
          pin: 2
        obj2:
          ID: 77
          pin: 3
      - obj1:
          ID: 77
          pin: 2
        obj2:
          ID: 79
          pin: 1
      - obj1:
          ID: 79
          pin: 2
        obj2:
          ID: 5
          pin: 2
      - obj1:
          ID: 79
          pin: 3
        obj2:
          ID: 81
          pin: 1
      - obj1:
          ID: 31
          pin: 2
        obj2:
          ID: 81
          pin: 4
      - obj1:
          ID: 81
          pin: 2
        obj2:
          ID: 35
          pin: 1
      - obj1:
          ID: 12
          pin: 2
        obj2:
          ID: 13
          pin: 1
      - obj1:
          ID: 13
          pin: 2
        obj2:
          ID: 14
          pin: 1
      - obj1:
          ID: 14
          pin: 2
        obj2:
          ID: 15
          pin: 1
      - obj1:
          ID: 24
          pin: 2
        obj2:
          ID: 25
          pin: 1
      - obj1:
          ID: 25
          pin: 2
        obj2:
          ID: 26
          pin: 1
      - obj1:
          ID: 26
          pin: 2
        obj2:
          ID: 27
          pin: 1
      - obj1:
          ID: 83
          pin: 2
        obj2:
          ID: 35
          pin: 3
      - obj1:
          ID: 83
          pin: 4
        obj2:
          ID: 28
          pin: 1
      - obj1:
          ID: 83
          pin: 1
        obj2:
          ID: 85
          pin: 3
      - obj1:
          ID: 31
          pin: 1
        obj2:
          ID: 85
          pin: 4
      - obj1:
          ID: 86
          pin: 2
        obj2:
          ID: 29
          pin: 1
      - obj1:
          ID: 86
          pin: 4
        obj2:
          ID: 36
          pin: 2
      - obj1:
          ID: 86
          pin: 1
        obj2:
          ID: 88
          pin: 3
      - obj1:
          ID: 32
          pin: 2
        obj2:
          ID: 88
          pin: 2
      - obj1:
          ID: 19
          pin: 1
        obj2:
          ID: 20
          pin: 1
      - obj1:
          ID: 89
          pin: 4
        obj2:
          ID: 12
          pin: 1
      - obj1:
          ID: 89
          pin: 3
        obj2:
          ID: 92
          pin: 2
      - obj1:
          ID: 89
          pin: 2
        obj2:
          ID: 11
          pin: 2
      - obj1:
          ID: 10
          pin: 1
        obj2:
          ID: 92
          pin: 3
      - obj1:
          ID: 94
          pin: 3
        obj2:
          ID: 97
          pin: 4
      - obj1:
          ID: 94
          pin: 4
        obj2:
          ID: 23
          pin: 2
      - obj1:
          ID: 94
          pin: 2
        obj2:
          ID: 27
          pin: 2
      - obj1:
          ID: 22
          pin: 1
        obj2:
          ID: 97
          pin: 3
      - obj1:
          ID: 99
          pin: 2
        obj2:
          ID: 36
          pin: 3
      - obj1:
          ID: 99
          pin: 3
        obj2:
          ID: 41
          pin: 1
      - obj1:
          ID: 99
          pin: 1
        obj2:
          ID: 103
          pin: 3
      - obj1:
          ID: 2
          pin: 1
        obj2:
          ID: 101
          pin: 1
      - obj1:
          ID: 101
          pin: 3
        obj2:
          ID: 102
          pin: 1
      - obj1:
          ID: 101
          pin: 2
        obj2:
          ID: 15
          pin: 2
      - obj1:
          ID: 102
          pin: 3
        obj2:
          ID: 103
          pin: 1
      - obj1:
          ID: 102
          pin: 2
        obj2:
          ID: 33
          pin: 3
      - obj1:
          ID: 103
          pin: 2
        obj2:
          ID: 16
          pin: 1
      - obj1:
          ID: 104
          pin: 4
        obj2:
          ID: 35
          pin: 2
      - obj1:
          ID: 104
          pin: 3
        obj2:
          ID: 40
          pin: 1
      - obj1:
          ID: 104
          pin: 1
        obj2:
          ID: 107
          pin: 3
      - obj1:
          ID: 1
          pin: 2
        obj2:
          ID: 106
          pin: 1
      - obj1:
          ID: 106
          pin: 3
        obj2:
          ID: 107
          pin: 1
      - obj1:
          ID: 106
          pin: 4
        obj2:
          ID: 24
          pin: 1
      - obj1:
          ID: 107
          pin: 4
        obj2:
          ID: 108
          pin: 2
      - obj1:
          ID: 34
          pin: 2
        obj2:
          ID: 108
          pin: 4
      - obj1:
          ID: 108
          pin: 3
        obj2:
          ID: 4
          pin: 1
      - obj1:
          ID: 110
          pin: 1
        obj2:
          ID: 115
          pin: 4
      - obj1:
          ID: 110
          pin: 3
        obj2:
          ID: 122
          pin: 4
      - obj1:
          ID: 110
          pin: 4
        obj2:
          ID: 37
          pin: 1
      - obj1:
          ID: 1
          pin: 1
        obj2:
          ID: 112
          pin: 3
      - obj1:
          ID: 112
          pin: 4
        obj2:
          ID: 113
          pin: 2
      - obj1:
          ID: 113
          pin: 3
        obj2:
          ID: 119
          pin: 1
      - obj1:
          ID: 113
          pin: 4
        obj2:
          ID: 114
          pin: 2
      - obj1:
          ID: 114
          pin: 3
        obj2:
          ID: 3
          pin: 1
      - obj1:
          ID: 114
          pin: 4
        obj2:
          ID: 115
          pin: 2
      - obj1:
          ID: 115
          pin: 3
        obj2:
          ID: 2
          pin: 2
      - obj1:
          ID: 23
          pin: 1
        obj2:
          ID: 119
          pin: 3
      - obj1:
          ID: 119
          pin: 4
        obj2:
          ID: 11
          pin: 1
      - obj1:
          ID: 30
          pin: 2
        obj2:
          ID: 122
          pin: 1
  TD:
    Expressions:
      - plot: 1
        x: t
        y: U(IN)
      - plot: 2
        x: t
        y: U(OUT)
      - plot: 3
        x: t
        y: I(RL)
      - plot: 4
        x: t
        y: I(VIN)
      - plot: 5
        x: t
        y: U(OUT)*I(RL)
    ExprRowOffset: 0
    IPNum: 1
    IP:
      - StartTime: 0.0
        EndTime: 0.5
        TimeStep: 1.0e-05
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
    NumPts: 101
    ScaleX: 2
    ScaleY: 1
    AvailScaleX: 3
    AvailScaleY: 3
    Expressions: []
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
