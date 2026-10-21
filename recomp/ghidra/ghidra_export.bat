@echo off
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot
set PATH=%JAVA_HOME%\bin;%PATH%
call D:\Drakengard_Recomp\tools\ghidra_12.1.4_PUBLIC\support\analyzeHeadless.bat D:\Drakengard_Recomp\recomp\ghidra\project Drakengard -process SLES_523.22 -noanalysis -scriptPath D:\Drakengard_Recomp\recomp\ghidra\scripts -postScript ExportPS2Functions.java
