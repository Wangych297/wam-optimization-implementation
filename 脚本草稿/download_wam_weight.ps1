$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$url='https://dl.fbaipublicfiles.com/watermark_anything/wam_mit.pth'
$dest='C:\Users\86155\Desktop\信息安全\大作业\参考论文\鲁棒图像水印资料\code\Watermark-Anything\checkpoints\wam_mit.pth'
Write-Output "START $(Get-Date -Format o) url=$url dest=$dest" | Out-File -FilePath 'C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\实验记录\wam_weight_download.log' -Encoding utf8
try {
  Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
  $fi=Get-Item -LiteralPath $dest
  Write-Output "DONE $(Get-Date -Format o) bytes=$($fi.Length)" | Out-File -FilePath 'C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\实验记录\wam_weight_download.log' -Append -Encoding utf8
} catch {
  Write-Output "ERROR $(Get-Date -Format o) $(.Exception.ToString())" | Out-File -FilePath 'C:\Users\86155\Desktop\信息安全\大作业\WAM-DWSF鲁棒水印任务\实验记录\wam_weight_download.log' -Append -Encoding utf8
  exit 1
}
