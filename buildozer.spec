[app]
title = Maybot
package.name = maybot
package.domain = org.akif.maybot
source.dir = .
source.include_exts = py
version = 1.0
requirements = python3,kivy,requests,gtts,pyjnius
orientation = portrait
fullscreen = 0

p4a.branch = develop
android.api = 36
android.minapi = 24
android.ndk_api = 24
android.ndk = 29
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True
android.permissions = INTERNET,ACCESS_NETWORK_STATE

[buildozer]
log_level = 2
warn_on_root = 1
