@echo off
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot
set PATH=%JAVA_HOME%\bin;%PATH%
call D:\Drakengard_Recomp\tools\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat D:\Drakengard_Recomp\recomp\ghidra\project Drakengard -import D:\Drakengard_Recomp\game\SLES_523.22 -overwrite -processor r5900:LE:32:default -scriptPath D:\Drakengard_Recomp\recomp\ghidra\scripts -postScript ExportPS2Functions.java -analysisTimeoutPerFile 7200 -max-cpu 14
