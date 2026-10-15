$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri "https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip" -OutFile "age_gender_models.zip"


Start-BitsTransfer -Source "https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip" -Destination "$PWD\age_gender_models.zip"


(New-Object System.Net.WebClient).DownloadFile("https://media.githubusercontent.com/media/Nikki1404/bu-div-de-cx-voice-mam/main/age_gender_models.zip", "$PWD\age_gender_models.zip")

(Get-Item age_gender_models.zip).Length / 1MB

Expand-Archive age_gender_models.zip -DestinationPath .
