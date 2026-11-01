# STAGES

<!-- omg:pin 8c295b0bf215bbc6fccf76a5614c0d6dff6ecea42808462db98df5364dac4951 -->
The single-file roll-up of every obsmage atom. Edit a block below and run
`omg_atoms.py unroll STAGES.md atoms/` to send the change back. Secret values never
appear here (`@secret(len=N)`). Generated; the pin above is the atoms it came from.

## demo/basic/profiles/Demo/basic.ini

```kv set=demo/basic/profiles/Demo/basic.ini/set-General.kv
Name=Demo
```

```kv set=demo/basic/profiles/Demo/basic.ini/set-Twitch.kv
Name=example
Token=@secret(len=21)
RefreshToken=@secret(len=25)
```

```kv set=demo/basic/profiles/Demo/basic.ini/set-Video.kv
BaseCX=1920
BaseCY=1080
```

```kv set=demo/basic/profiles/Demo/basic.ini/set-WebsocketAPI.kv
ServerPort=4444
AuthSecret=@secret(len=22)
```

## demo/basic/profiles/Demo/service.json

```kv set=demo/basic/profiles/Demo/service.json/_all.kv
/settings/bwtest:=false
/settings/key:="@secret(len=27)"
/settings/server:="rtmp://example.invalid/live"
/settings/service:="Custom"
/type:="rtmp_custom"
```

## demo/basic/scenes/Demo.json

```kv set=demo/basic/scenes/Demo.json/_top.kv
/current_scene:="Main"
/name:="Demo"
/scene_order/#0/name:="Main"
/groups:=[]
/transitions:=[]
```

## demo/basic/scenes/Demo.json/sources

```kv set=demo/basic/scenes/Demo.json/sources/000-Left.kv
/sources/#0/id:="monitor_capture"
/sources/#0/name:="Left"
/sources/#0/settings/monitor:=1
/sources/#0/settings/capture_cursor:=true
/sources/#0/filters:=[]
```

```kv set=demo/basic/scenes/Demo.json/sources/001-Right.kv
/sources/#1/id:="monitor_capture"
/sources/#1/name:="Right"
/sources/#1/settings/monitor_id:="\\\\?\\DISPLAY#EXA0001#1&0&UID1#{guid}"
```

```kv set=demo/basic/scenes/Demo.json/sources/002-Lower_third.kv
/sources/#2/id:="text_gdiplus"
/sources/#2/name:="Lower third"
/sources/#2/settings/text:="line one\nline = two: three"
/sources/#2/settings/font/face:="Arial"
/sources/#2/settings/font/size:=48
```

```kv set=demo/basic/scenes/Demo.json/sources/003-Main.kv
/sources/#3/id:="scene"
/sources/#3/name:="Main"
/sources/#3/settings/items/#0/name:="Left"
/sources/#3/settings/items/#0/id:=1
/sources/#3/settings/items/#0/pos/x:=0.0
/sources/#3/settings/items/#0/pos/y:=0.0
/sources/#3/settings/items/#0/scale/x:=0.5
/sources/#3/settings/items/#0/scale/y:=0.5
/sources/#3/settings/items/#0/visible:=true
/sources/#3/settings/items/#1/name:="Right"
/sources/#3/settings/items/#1/id:=2
/sources/#3/settings/items/#1/pos/x:=960.0
/sources/#3/settings/items/#1/pos/y:=0.0
/sources/#3/settings/items/#1/scale/x:=0.5
/sources/#3/settings/items/#1/scale/y:=0.5
/sources/#3/settings/items/#1/visible:=false
/sources/#3/settings/custom_size:=false
```

## demo/global.ini

```kv set=demo/global.ini/set-Basic.kv
Profile=Demo
SceneCollection=Demo
```

```kv set=demo/global.ini/set-General.kv
FirstRun=true
```

