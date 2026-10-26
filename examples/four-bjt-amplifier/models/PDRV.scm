scm:
  MajorVersion: 5
  MinorVersion: 1
  General:
    Scale: 57
    HPos: 870
    VPos: 760
    SWidth: 3000
    SHeight: 3000
  Special:
    LangVersion: 2
  Scheme:
    MajorSchVer: 3
    MinorSchVer: 0
    Objects:
      - ID: 1
        Type: 1000
        Name: RB
        X: 600
        Y: 760
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 0.1
      - ID: 2
        Type: 1000
        Name: RC
        X: 1048
        Y: 1040
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 0.01
      - ID: 3
        Type: 1000
        Name: RE
        X: 952
        Y: 480
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          R: 0.01
      - ID: 4
        Type: 1101
        Name: DBE
        X: 1200
        Y: 624
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 8.099999999999964
          Roff: 80999999999.99963
          Uon: 0.65
      - ID: 5
        Type: 1101
        Name: DBC
        X: 800
        Y: 896
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          Ron: 0.10125
          Roff: 1012500000.0
          Uon: 0.65
      - ID: 6
        Type: 6002
        Name: FF
        X: 1000
        Y: 640
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          h: -79.99999999999964
      - ID: 7
        Type: 6002
        Name: FR
        X: 1000
        Y: 880
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
        Params:
          h: -1.0
      - ID: 8
        Type: 400
        Name: B
        X: 400
        Y: 760
        Rot: 2
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 9
        Type: 400
        Name: E
        X: 952
        Y: 360
        Rot: 3
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 10
        Type: 400
        Name: C
        X: 1048
        Y: 1160
        Rot: 1
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 11
        Type: 300
        Name: CON11
        X: 952
        Y: 624
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 12
        Type: 300
        Name: CON12
        X: 952
        Y: 648
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 15
        Type: 300
        Name: CON15
        X: 1048
        Y: 872
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 16
        Type: 300
        Name: CON16
        X: 1048
        Y: 896
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 18
        Type: 300
        Name: CON18
        X: 660
        Y: 760
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
      - ID: 20
        Type: 300
        Name: CON20
        X: 1280
        Y: 512
        Rot: 0
        FlipV: 0
        FlipH: 0
        active_property_page: 0
    Wires:
      - obj1:
          ID: 3
          pin: 2
        obj2:
          ID: 11
          pin: 2
      - obj1:
          ID: 11
          pin: 4
        obj2:
          ID: 12
          pin: 2
      - obj1:
          ID: 11
          pin: 3
        obj2:
          ID: 6
          pin: 2
      - obj1:
          ID: 12
          pin: 4
        obj2:
          ID: 7
          pin: 3
      - obj1:
          ID: 12
          pin: 3
        obj2:
          ID: 6
          pin: 4
      - obj1:
          ID: 6
          pin: 3
        obj2:
          ID: 15
          pin: 2
      - obj1:
          ID: 7
          pin: 4
        obj2:
          ID: 15
          pin: 1
      - obj1:
          ID: 7
          pin: 2
        obj2:
          ID: 16
          pin: 1
      - obj1:
          ID: 15
          pin: 4
        obj2:
          ID: 16
          pin: 2
      - obj1:
          ID: 16
          pin: 4
        obj2:
          ID: 2
          pin: 2
      - obj1:
          ID: 1
          pin: 2
        obj2:
          ID: 18
          pin: 1
      - obj1:
          ID: 18
          pin: 2
        obj2:
          ID: 20
          pin: 1
      - obj1:
          ID: 18
          pin: 4
        obj2:
          ID: 5
          pin: 2
      - obj1:
          ID: 4
          pin: 2
        obj2:
          ID: 20
          pin: 4
      - obj1:
          ID: 8
          pin: 1
        obj2:
          ID: 1
          pin: 1
      - obj1:
          ID: 5
          pin: 1
        obj2:
          ID: 7
          pin: 1
      - obj1:
          ID: 9
          pin: 1
        obj2:
          ID: 3
          pin: 1
      - obj1:
          ID: 6
          pin: 1
        obj2:
          ID: 4
          pin: 1
      - obj1:
          ID: 2
          pin: 1
        obj2:
          ID: 10
          pin: 1
  TD:
    Expressions:
      - plot: 1
        x: t
        y: U(B)
    ExprRowOffset: 0
    IPNum: 1
    IP:
      - StartTime: 0
        EndTime: 0.005
        TimeStep: 1.0e-06
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
    StartFreq: 10
    EndFreq: 100000
    NumPts: 100
    ScaleX: 2
    ScaleY: 1
    AvailScaleX: 3
    AvailScaleY: 3
    Expressions:
      - plot: 1
        x: f
        y: db(U(B))
      - plot: 2
        x: f
        y: phs(U(B))
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
