$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri "https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip" -OutFile "age_gender_models.zip"


Start-BitsTransfer -Source "https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip" -Destination "$PWD\age_gender_models.zip"


(New-Object System.Net.WebClient).DownloadFile("https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip", "$PWD\age_gender_models.zip")

(Get-Item age_gender_models.zip).Length / 1MB

Expand-Archive age_gender_models.zip -DestinationPath .


python3 -c "
import urllib.request, sys
url = 'https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip'
def hook(b, bs, total):
    sys.stdout.write(f'\r{min(b*bs, total)/1e6:.0f} / {total/1e6:.0f} MB'); sys.stdout.flush()
urllib.request.urlretrieve(url, 'age_gender_models.zip', hook)
print('\ndone')
"

Start-BitsTransfer -Source "https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip" -Destination "$PWD\age_gender_models.zip"


(New-Object System.Net.WebClient).DownloadFile("https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip", "$PWD\age_gender_models.zip")
