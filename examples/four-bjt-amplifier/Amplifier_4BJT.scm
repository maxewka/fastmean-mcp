scm:
  MajorVersion: 5
  MinorVersion: 1
  General:
    Scale: 100
    HPos: 1422
    VPos: 1200
    SWidth: 3280
    SHeight: 3330
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
            U0: Vi
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
          R: Rf
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
          R: Rf
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
        Y: 640
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 38
        Type: 200
        Name: GND2
        X: 240
        Y: 1680
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 39
        Type: 200
        Name: GND3
        X: 240
        Y: 1280
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 40
        Type: 200
        Name: GND4
        X: 460
        Y: 1280
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 41
        Type: 200
        Name: GND5
        X: 460
        Y: 1040
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 42
        Type: 200
        Name: GND6
        X: 2200
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 43
        Type: 400
        Name: IN
        X: 440
        Y: 1160
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 44
        Type: 400
        Name: OUT
        X: 2400
        Y: 1160
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 45
        Type: 400
        Name: VPP
        X: 2400
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 46
        Type: 400
        Name: VNN
        X: 2400
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 47
        Type: 300
        Name: CON47
        X: 1260
        Y: 400
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 48
        Type: 300
        Name: CON48
        X: 1260
        Y: 1728
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 51
        Type: 300
        Name: CON51
        X: 1860
        Y: 1728
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 52
        Type: 300
        Name: CON52
        X: 1880
        Y: 1140
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 54
        Type: 300
        Name: CON54
        X: 2120
        Y: 620
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
        X: 2200
        Y: 1160
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 59
        Type: 300
        Name: CON59
        X: 760
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 60
        Type: 300
        Name: CON60
        X: 1076
        Y: 320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 62
        Type: 300
        Name: CON62
        X: 1160
        Y: 408
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 64
        Type: 300
        Name: CON64
        X: 1608
        Y: 440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 65
        Type: 300
        Name: CON65
        X: 1608
        Y: 808
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 68
        Type: 300
        Name: CON68
        X: 1880
        Y: 328
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 71
        Type: 300
        Name: CON71
        X: 2380
        Y: 328
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 73
        Type: 300
        Name: CON73
        X: 2560
        Y: 1352
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 75
        Type: 300
        Name: CON75
        X: 760
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 77
        Type: 300
        Name: CON77
        X: 1076
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 78
        Type: 300
        Name: CON78
        X: 1160
        Y: 1912
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 79
        Type: 300
        Name: CON79
        X: 1580
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 80
        Type: 300
        Name: CON80
        X: 1880
        Y: 2000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 83
        Type: 300
        Name: CON83
        X: 412
        Y: 1112
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 86
        Type: 300
        Name: CON86
        X: 460
        Y: 1160
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 88
        Type: 300
        Name: CON88
        X: 956
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 89
        Type: 300
        Name: CON89
        X: 980
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 90
        Type: 300
        Name: CON90
        X: 956
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 92
        Type: 300
        Name: CON92
        X: 980
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 94
        Type: 300
        Name: CON94
        X: 224
        Y: 2080
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 96
        Type: 300
        Name: CON96
        X: 564
        Y: 1832
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 97
        Type: 300
        Name: CON97
        X: 1160
        Y: 1368
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 99
        Type: 300
        Name: CON99
        X: 1540
        Y: 1440
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 101
        Type: 300
        Name: CON101
        X: 1580
        Y: 1484
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 103
        Type: 300
        Name: CON103
        X: 1660
        Y: 1280
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 104
        Type: 300
        Name: CON104
        X: 1668
        Y: 432
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 107
        Type: 300
        Name: CON107
        X: 1772
        Y: 1484
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 108
        Type: 300
        Name: CON108
        X: 1900
        Y: 648
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 109
        Type: 300
        Name: CON109
        X: 1900
        Y: 832
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 111
        Type: 300
        Name: CON111
        X: 2560
        Y: 2080
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 112
        Type: 300
        Name: CON112
        X: 1160
        Y: 1370
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 113
        Type: 300
        Name: CON113
        X: 1580
        Y: 1296
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 114
        Type: 300
        Name: CON114
        X: 1580
        Y: 1370
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 116
        Type: 300
        Name: CON116
        X: 1696
        Y: 1208
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 118
        Type: 300
        Name: CON118
        X: 1772
        Y: 968
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 120
        Type: 300
        Name: CON120
        X: 1820
        Y: 1208
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 122
        Type: 300
        Name: CON122
        X: 760
        Y: 920
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 125
        Type: 300
        Name: CON125
        X: 1012
        Y: 680
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 127
        Type: 300
        Name: CON127
        X: 1076
        Y: 872
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 130
        Type: 300
        Name: CON130
        X: 760
        Y: 1372
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 133
        Type: 300
        Name: CON133
        X: 1012
        Y: 1640
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 135
        Type: 300
        Name: CON135
        X: 1076
        Y: 1460
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 136
        Type: 300
        Name: CON136
        X: 1580
        Y: 620
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 137
        Type: 300
        Name: CON137
        X: 1580
        Y: 1700
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 139
        Type: 300
        Name: CON139
        X: 1860
        Y: 1040
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 140
        Type: 300
        Name: CON140
        X: 1880
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 142
        Type: 300
        Name: CON142
        X: 1860
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 143
        Type: 300
        Name: CON143
        X: 1880
        Y: 1320
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 145
        Type: 300
        Name: CON145
        X: 740
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 146
        Type: 300
        Name: CON146
        X: 772
        Y: 820
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 149
        Type: 300
        Name: CON149
        X: 740
        Y: 1500
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 151
        Type: 300
        Name: CON151
        X: 772
        Y: 1500
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 152
        Type: 900
        Name: MCP_NOTE_152
        X: 224
        Y: 2200
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: ".parameter\r\nRload=1.25 \"Rload [ohm]\";\r\nRf=2958.192887903313 \"Rf [ohm]\";\r\nCinput=0.001 \"Cinput\
            \ [F]\";\r\nCbootstrap=0.01 \"Cbootstrap [F]\";\r\nRbias=69.04195248892718 \"Rbias [ohm]\";\r\nVrail=38 \"Vrail\
            \ [V]\";\r\nVi=1.4142135623730951 \"Vi [V]\";\r\n"
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
      - ID: 153
        Type: 900
        Name: MCP_NOTE_153
        X: 224
        Y: 2411
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
      - ID: 154
        Type: 900
        Name: MCP_NOTE_154
        X: 224
        Y: 2490
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
      - ID: 155
        Type: 900
        Name: MCP_NOTE_155
        X: 224
        Y: 2569
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
      - ID: 156
        Type: 900
        Name: MCP_NOTE_156
        X: 224
        Y: 2648
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
      - ID: 157
        Type: 900
        Name: MCP_NOTE_157
        X: 224
        Y: 2727
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
      - ID: 158
        Type: 900
        Name: MCP_NOTE_158
        X: 224
        Y: 2806
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "I(VIN) — ток входного источника.\r\nНоминально66,8 мА RMS, пик94,5 мА. Vi — амплитуда, не RMS."
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
      - ID: 159
        Type: 900
        Name: MCP_NOTE_159
        X: 224
        Y: 2885
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
      - ID: 160
        Type: 900
        Name: MCP_NOTE_160
        X: 224
        Y: 2986
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: "Параметры: Rload — нагрузка; Rf — обе цепи ОС;\r\nCinput/Cbootstrap — парные ёмкости; Rbias — настройка смещения."
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
      - ID: 161
        Type: 900
        Name: MCP_NOTE_161
        X: 224
        Y: 3065
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
      - ID: 162
        Type: 900
        Name: MCP_NOTE_162
        X: 224
        Y: 3144
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
          ID: 21
          pin: 1
        obj2:
          ID: 47
          pin: 1
      - obj1:
          ID: 9
          pin: 1
        obj2:
          ID: 48
          pin: 4
      - obj1:
          ID: 47
          pin: 4
        obj2:
          ID: 48
          pin: 2
      - obj1:
          ID: 47
          pin: 3
        obj2:
          ID: 54
          pin: 2
      - obj1:
          ID: 48
          pin: 3
        obj2:
          ID: 51
          pin: 1
      - obj1:
          ID: 6
          pin: 2
        obj2:
          ID: 54
          pin: 1
      - obj1:
          ID: 18
          pin: 2
        obj2:
          ID: 51
          pin: 2
      - obj1:
          ID: 28
          pin: 2
        obj2:
          ID: 52
          pin: 2
      - obj1:
          ID: 52
          pin: 4
        obj2:
          ID: 29
          pin: 2
      - obj1:
          ID: 52
          pin: 3
        obj2:
          ID: 55
          pin: 1
      - obj1:
          ID: 54
          pin: 4
        obj2:
          ID: 55
          pin: 2
      - obj1:
          ID: 55
          pin: 4
        obj2:
          ID: 57
          pin: 1
      - obj1:
          ID: 57
          pin: 4
        obj2:
          ID: 30
          pin: 1
      - obj1:
          ID: 57
          pin: 3
        obj2:
          ID: 44
          pin: 1
      - obj1:
          ID: 1
          pin: 2
        obj2:
          ID: 59
          pin: 1
      - obj1:
          ID: 59
          pin: 4
        obj2:
          ID: 24
          pin: 1
      - obj1:
          ID: 59
          pin: 3
        obj2:
          ID: 60
          pin: 1
      - obj1:
          ID: 60
          pin: 4
        obj2:
          ID: 62
          pin: 1
      - obj1:
          ID: 60
          pin: 3
        obj2:
          ID: 68
          pin: 2
      - obj1:
          ID: 62
          pin: 4
        obj2:
          ID: 34
          pin: 2
      - obj1:
          ID: 4
          pin: 1
        obj2:
          ID: 64
          pin: 1
      - obj1:
          ID: 64
          pin: 4
        obj2:
          ID: 65
          pin: 2
      - obj1:
          ID: 65
          pin: 4
        obj2:
          ID: 73
          pin: 1
      - obj1:
          ID: 65
          pin: 3
        obj2:
          ID: 35
          pin: 2
      - obj1:
          ID: 68
          pin: 3
        obj2:
          ID: 71
          pin: 1
      - obj1:
          ID: 71
          pin: 2
        obj2:
          ID: 45
          pin: 1
      - obj1:
          ID: 71
          pin: 3
        obj2:
          ID: 73
          pin: 2
      - obj1:
          ID: 2
          pin: 1
        obj2:
          ID: 75
          pin: 1
      - obj1:
          ID: 15
          pin: 2
        obj2:
          ID: 75
          pin: 2
      - obj1:
          ID: 75
          pin: 3
        obj2:
          ID: 77
          pin: 1
      - obj1:
          ID: 77
          pin: 2
        obj2:
          ID: 78
          pin: 1
      - obj1:
          ID: 77
          pin: 3
        obj2:
          ID: 79
          pin: 1
      - obj1:
          ID: 33
          pin: 3
        obj2:
          ID: 78
          pin: 2
      - obj1:
          ID: 16
          pin: 1
        obj2:
          ID: 79
          pin: 2
      - obj1:
          ID: 79
          pin: 3
        obj2:
          ID: 80
          pin: 1
      - obj1:
          ID: 36
          pin: 3
        obj2:
          ID: 80
          pin: 2
      - obj1:
          ID: 80
          pin: 3
        obj2:
          ID: 46
          pin: 1
      - obj1:
          ID: 3
          pin: 2
        obj2:
          ID: 83
          pin: 1
      - obj1:
          ID: 83
          pin: 2
        obj2:
          ID: 19
          pin: 2
      - obj1:
          ID: 83
          pin: 4
        obj2:
          ID: 7
          pin: 2
      - obj1:
          ID: 83
          pin: 3
        obj2:
          ID: 86
          pin: 2
      - obj1:
          ID: 43
          pin: 1
        obj2:
          ID: 86
          pin: 1
      - obj1:
          ID: 20
          pin: 2
        obj2:
          ID: 88
          pin: 1
      - obj1:
          ID: 88
          pin: 2
        obj2:
          ID: 21
          pin: 2
      - obj1:
          ID: 88
          pin: 3
        obj2:
          ID: 89
          pin: 1
      - obj1:
          ID: 22
          pin: 2
        obj2:
          ID: 89
          pin: 2
      - obj1:
          ID: 89
          pin: 3
        obj2:
          ID: 34
          pin: 1
      - obj1:
          ID: 8
          pin: 2
        obj2:
          ID: 90
          pin: 1
      - obj1:
          ID: 90
          pin: 4
        obj2:
          ID: 9
          pin: 2
      - obj1:
          ID: 90
          pin: 3
        obj2:
          ID: 92
          pin: 1
      - obj1:
          ID: 92
          pin: 4
        obj2:
          ID: 10
          pin: 2
      - obj1:
          ID: 92
          pin: 3
        obj2:
          ID: 33
          pin: 1
      - obj1:
          ID: 94
          pin: 2
        obj2:
          ID: 96
          pin: 1
      - obj1:
          ID: 94
          pin: 3
        obj2:
          ID: 111
          pin: 1
      - obj1:
          ID: 96
          pin: 2
        obj2:
          ID: 97
          pin: 1
      - obj1:
          ID: 34
          pin: 3
        obj2:
          ID: 97
          pin: 2
      - obj1:
          ID: 99
          pin: 2
        obj2:
          ID: 104
          pin: 1
      - obj1:
          ID: 99
          pin: 3
        obj2:
          ID: 101
          pin: 2
      - obj1:
          ID: 101
          pin: 4
        obj2:
          ID: 17
          pin: 2
      - obj1:
          ID: 101
          pin: 3
        obj2:
          ID: 107
          pin: 1
      - obj1:
          ID: 103
          pin: 2
        obj2:
          ID: 109
          pin: 1
      - obj1:
          ID: 103
          pin: 3
        obj2:
          ID: 32
          pin: 1
      - obj1:
          ID: 104
          pin: 4
        obj2:
          ID: 108
          pin: 1
      - obj1:
          ID: 107
          pin: 2
        obj2:
          ID: 36
          pin: 1
      - obj1:
          ID: 107
          pin: 3
        obj2:
          ID: 111
          pin: 2
      - obj1:
          ID: 108
          pin: 4
        obj2:
          ID: 109
          pin: 2
      - obj1:
          ID: 112
          pin: 4
        obj2:
          ID: 33
          pin: 2
      - obj1:
          ID: 112
          pin: 3
        obj2:
          ID: 114
          pin: 1
      - obj1:
          ID: 5
          pin: 2
        obj2:
          ID: 113
          pin: 2
      - obj1:
          ID: 113
          pin: 4
        obj2:
          ID: 114
          pin: 2
      - obj1:
          ID: 113
          pin: 3
        obj2:
          ID: 120
          pin: 4
      - obj1:
          ID: 116
          pin: 2
        obj2:
          ID: 31
          pin: 2
      - obj1:
          ID: 116
          pin: 3
        obj2:
          ID: 120
          pin: 1
      - obj1:
          ID: 118
          pin: 2
        obj2:
          ID: 35
          pin: 1
      - obj1:
          ID: 118
          pin: 3
        obj2:
          ID: 120
          pin: 2
      - obj1:
          ID: 23
          pin: 2
        obj2:
          ID: 122
          pin: 4
      - obj1:
          ID: 27
          pin: 2
        obj2:
          ID: 122
          pin: 2
      - obj1:
          ID: 122
          pin: 3
        obj2:
          ID: 127
          pin: 4
      - obj1:
          ID: 22
          pin: 1
        obj2:
          ID: 125
          pin: 1
      - obj1:
          ID: 125
          pin: 4
        obj2:
          ID: 127
          pin: 1
      - obj1:
          ID: 11
          pin: 2
        obj2:
          ID: 130
          pin: 2
      - obj1:
          ID: 130
          pin: 4
        obj2:
          ID: 12
          pin: 1
      - obj1:
          ID: 130
          pin: 3
        obj2:
          ID: 135
          pin: 2
      - obj1:
          ID: 10
          pin: 1
        obj2:
          ID: 133
          pin: 1
      - obj1:
          ID: 133
          pin: 2
        obj2:
          ID: 135
          pin: 1
      - obj1:
          ID: 4
          pin: 2
        obj2:
          ID: 136
          pin: 2
      - obj1:
          ID: 136
          pin: 4
        obj2:
          ID: 5
          pin: 1
      - obj1:
          ID: 136
          pin: 3
        obj2:
          ID: 6
          pin: 1
      - obj1:
          ID: 17
          pin: 1
        obj2:
          ID: 137
          pin: 2
      - obj1:
          ID: 137
          pin: 4
        obj2:
          ID: 16
          pin: 2
      - obj1:
          ID: 137
          pin: 3
        obj2:
          ID: 18
          pin: 1
      - obj1:
          ID: 31
          pin: 1
        obj2:
          ID: 139
          pin: 1
      - obj1:
          ID: 139
          pin: 2
        obj2:
          ID: 140
          pin: 1
      - obj1:
          ID: 35
          pin: 3
        obj2:
          ID: 140
          pin: 2
      - obj1:
          ID: 140
          pin: 4
        obj2:
          ID: 28
          pin: 1
      - obj1:
          ID: 32
          pin: 2
        obj2:
          ID: 142
          pin: 2
      - obj1:
          ID: 142
          pin: 3
        obj2:
          ID: 143
          pin: 1
      - obj1:
          ID: 29
          pin: 1
        obj2:
          ID: 143
          pin: 2
      - obj1:
          ID: 143
          pin: 4
        obj2:
          ID: 36
          pin: 2
      - obj1:
          ID: 19
          pin: 1
        obj2:
          ID: 145
          pin: 1
      - obj1:
          ID: 145
          pin: 2
        obj2:
          ID: 146
          pin: 1
      - obj1:
          ID: 146
          pin: 4
        obj2:
          ID: 20
          pin: 1
      - obj1:
          ID: 7
          pin: 1
        obj2:
          ID: 149
          pin: 2
      - obj1:
          ID: 149
          pin: 3
        obj2:
          ID: 151
          pin: 1
      - obj1:
          ID: 151
          pin: 2
        obj2:
          ID: 8
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
          ID: 1
          pin: 1
        obj2:
          ID: 37
          pin: 1
      - obj1:
          ID: 3
          pin: 1
        obj2:
          ID: 39
          pin: 1
      - obj1:
          ID: 38
          pin: 1
        obj2:
          ID: 2
          pin: 2
      - obj1:
          ID: 41
          pin: 1
        obj2:
          ID: 23
          pin: 1
      - obj1:
          ID: 40
          pin: 1
        obj2:
          ID: 11
          pin: 1
      - obj1:
          ID: 30
          pin: 2
        obj2:
          ID: 42
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
