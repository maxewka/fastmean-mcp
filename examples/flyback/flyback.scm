scm:
  MajorVersion: 5
  MinorVersion: 1
  General:
    Scale: 46
    HPos: 1150
    VPos: 870
    SWidth: 3000
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
        X: 400
        Y: 720
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          ST: 1
          DC:
            U0: 24.0
            Delay: 0
            TFR: 1n
          AC:
            U0: 24.0
            F: 1000
            PHI0: 0
            FD: 0
            NP: 1
            Delay: 0
          PULSE:
            F: 1000
            K: 50
            UMAX: 24.0
            UMIN: 0
            TFR: 1n
            Delay: 0
          TRIANG:
            F: 1000
            K: 50
            UMAX: 24.0
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
        Type: 1002
        Name: LM
        X: 760
        Y: 720
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          L: 0.00019999999999999998
          IC: 0.0
      - ID: 3
        Type: 6101
        Name: TR1
        X: 1000
        Y: 720
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          n: 1.0
      - ID: 4
        Type: 6600
        Name: SW1
        X: 760
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.05
          Roff: 10000000.0
          Uon: 3.0
          Uoff: 2.0
      - ID: 5
        Type: 2010
        Name: PWM
        X: 400
        Y: 1000
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          ST: 3
          DC:
            U0: 5.0
            Delay: 0
            TFR: 1n
          AC:
            U0: 5.0
            F: 1000
            PHI0: 0
            FD: 0
            NP: 1
            Delay: 0
          PULSE:
            F: 50000.0
            K: 40.0
            UMAX: 5.0
            UMIN: 0.0
            TFR: 2.0e-08
            Delay: 2.0000000000000002e-07
          TRIANG:
            F: 1000
            K: 50
            UMAX: 5.0
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
      - ID: 6
        Type: 1101
        Name: DOUT
        X: 1280
        Y: 752
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.05
          Roff: 10000000.0
          Uon: 0.3
      - ID: 7
        Type: 1001
        Name: COUT
        X: 1520
        Y: 880
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          C: 4.7e-05
          IC: 0.0
      - ID: 8
        Type: 1000
        Name: RL
        X: 1760
        Y: 880
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 20.0
      - ID: 9
        Type: 200
        Name: GND1
        X: 400
        Y: 840
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 10
        Type: 200
        Name: GND2
        X: 1104
        Y: 688
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 11
        Type: 200
        Name: GND3
        X: 744
        Y: 1108
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 12
        Type: 200
        Name: GND4
        X: 776
        Y: 1108
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 13
        Type: 200
        Name: GND5
        X: 400
        Y: 1120
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 14
        Type: 200
        Name: GND6
        X: 1520
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 15
        Type: 200
        Name: GND7
        X: 1760
        Y: 1000
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 16
        Type: 400
        Name: in
        X: 400
        Y: 620
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 17
        Type: 400
        Name: out
        X: 1840
        Y: 752
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 18
        Type: 400
        Name: drain
        X: 920
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 19
        Type: 400
        Name: gate
        X: 400
        Y: 900
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 20
        Type: 300
        Name: CON20
        X: 400
        Y: 660
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 21
        Type: 300
        Name: CON21
        X: 744
        Y: 660
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 25
        Type: 300
        Name: CON25
        X: 776
        Y: 780
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 26
        Type: 300
        Name: CON26
        X: 776
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 28
        Type: 300
        Name: CON28
        X: 916
        Y: 880
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 30
        Type: 300
        Name: CON30
        X: 1520
        Y: 820
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 32
        Type: 300
        Name: CON32
        X: 1760
        Y: 820
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 33
        Type: 300
        Name: CON33
        X: 400
        Y: 952
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 34
        Type: 900
        Name: MCP_NOTE_34
        X: 400
        Y: 1240
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: 'Flyback: native TR transformer, magnetizing LM and voltage-controlled SW.'
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
      - ID: 35
        Type: 900
        Name: MCP_NOTE_35
        X: 400
        Y: 1297
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Text: Open-loop educational model; no saturation, leakage or transistor parasitics.
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
          ID: 16
          pin: 1
        obj2:
          ID: 20
          pin: 2
      - obj1:
          ID: 20
          pin: 4
        obj2:
          ID: 1
          pin: 2
      - obj1:
          ID: 20
          pin: 3
        obj2:
          ID: 21
          pin: 1
      - obj1:
          ID: 21
          pin: 4
        obj2:
          ID: 3
          pin: 1
      - obj1:
          ID: 21
          pin: 3
        obj2:
          ID: 2
          pin: 1
      - obj1:
          ID: 2
          pin: 2
        obj2:
          ID: 25
          pin: 1
      - obj1:
          ID: 25
          pin: 4
        obj2:
          ID: 26
          pin: 2
      - obj1:
          ID: 26
          pin: 4
        obj2:
          ID: 4
          pin: 3
      - obj1:
          ID: 26
          pin: 3
        obj2:
          ID: 28
          pin: 1
      - obj1:
          ID: 28
          pin: 2
        obj2:
          ID: 3
          pin: 2
      - obj1:
          ID: 28
          pin: 3
        obj2:
          ID: 18
          pin: 1
      - obj1:
          ID: 6
          pin: 2
        obj2:
          ID: 30
          pin: 2
      - obj1:
          ID: 30
          pin: 4
        obj2:
          ID: 7
          pin: 1
      - obj1:
          ID: 30
          pin: 3
        obj2:
          ID: 32
          pin: 1
      - obj1:
          ID: 32
          pin: 2
        obj2:
          ID: 17
          pin: 1
      - obj1:
          ID: 32
          pin: 4
        obj2:
          ID: 8
          pin: 1
      - obj1:
          ID: 19
          pin: 1
        obj2:
          ID: 33
          pin: 2
      - obj1:
          ID: 33
          pin: 4
        obj2:
          ID: 5
          pin: 2
      - obj1:
          ID: 33
          pin: 3
        obj2:
          ID: 4
          pin: 1
      - obj1:
          ID: 3
          pin: 4
        obj2:
          ID: 6
          pin: 1
      - obj1:
          ID: 1
          pin: 1
        obj2:
          ID: 9
          pin: 1
      - obj1:
          ID: 5
          pin: 1
        obj2:
          ID: 13
          pin: 1
      - obj1:
          ID: 4
          pin: 2
        obj2:
          ID: 11
          pin: 1
      - obj1:
          ID: 4
          pin: 4
        obj2:
          ID: 12
          pin: 1
      - obj1:
          ID: 3
          pin: 3
        obj2:
          ID: 10
          pin: 1
      - obj1:
          ID: 7
          pin: 2
        obj2:
          ID: 14
          pin: 1
      - obj1:
          ID: 8
          pin: 2
        obj2:
          ID: 15
          pin: 1
  TD:
    Expressions:
      - plot: 1
        x: t
        y: U(out)
      - plot: 2
        x: t
        y: U(drain)
      - plot: 3
        x: t
        y: I(LM)
      - plot: 4
        x: t
        y: I(DOUT)
      - plot: 5
        x: t
        y: U(gate)
    ExprRowOffset: 0
    IPNum: 1
    IP:
      - StartTime: 0
        EndTime: 0.01
        TimeStep: 1.0000000000000001e-07
        NumPts: 100
        PtsStepFl: 2
        EPS: 1.0e-05
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
    StartFreq: 10
    EndFreq: 100000
    NumPts: 100
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
