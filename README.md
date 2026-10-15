# Voice IQ API (MaM)

One FastAPI service combines voice biometrics and age/gender profiling. Profiling uses the **MaM** CNN (Multi-Attention Module, [Anvarjon/Age-Gender-Classification](https://github.com/Anvarjon/Age-Gender-Classification)) instead of VoxProfile. The UI is served from the same origin, so the browser sends each selected recording to the same API host.

Everything runs on CPU. MaM is a small CNN on a 64×64 spectrogram, and the speaker engine is CPU-only, so no GPU or CUDA image is needed.

## MaM weights

The trained weights in `age_gender_models/` are copied into the image at `/models` at build time, so Cloud Run needs no extra storage for them. These are the files published by the MaM author:

```
age_gender_models/
├── age_classification_acc_81.h5
├── gender_classification_acc_96.h5
└── gender_age_classification_acc_80.h5
```

The training repo's layout (`age/best_model_age.h5`, `gender/best_model_gender.h5`, `gender_age/best_model_gender_age.h5`) is also accepted, for weights you train yourself. Age and gender each use their own head when it is present. If only `gender_age` is present, age and gender are derived from it by summing its probabilities. Startup fails if the loaded heads cannot produce both age and gender.

## Deploy: GCP VM -> Artifact Registry -> Cloud Run

Build on a GCP VM, push the image to Artifact Registry, and deploy it to Cloud Run. Set these variables first and use them in every step:

```bash
PROJECT_ID=your-project-id
REGION=asia-south1
ZONE=asia-south1-a
VM=voice-iq-build
REPO=voice-iq
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/voice-iq-mam:v1
BUCKET=$PROJECT_ID-voice-iq-data
SERVICE=voice-iq-mam
```

### 1. One-time GCP setup (from your machine)

```bash
gcloud config set project $PROJECT_ID
gcloud services enable compute.googleapis.com artifactregistry.googleapis.com run.googleapis.com storage.googleapis.com

gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION

gcloud storage buckets create gs://$BUCKET --location=$REGION --uniform-bucket-level-access

PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectUser
```

### 2. Create the build VM and copy the project to it

`--scopes=cloud-platform` lets the VM push to Artifact Registry; the default VM scopes are read-only.

```bash
gcloud compute instances create $VM --zone=$ZONE \
  --machine-type=e2-standard-4 --boot-disk-size=50GB \
  --image-family=ubuntu-2204-lts --image-project=ubuntu-os-cloud \
  --scopes=cloud-platform

cd /Users/nikita/Documents/bu-div-de-cx-voice-mam
gcloud compute scp --recurse --zone=$ZONE ./ $VM:~/voice-iq-mam
gcloud compute ssh $VM --zone=$ZONE
```

### 3. On the VM: build, check, push

Set the same variables again inside the VM, then:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

cd ~/voice-iq-mam
docker build -t $IMAGE .

docker run --rm $IMAGE python -c "from models.age_gender_model import age_gender_model as m; m.load(); print('OK:', m.loaded_tasks)"

gcloud auth configure-docker $REGION-docker.pkg.dev --quiet
docker push $IMAGE
```

### 4. Deploy to Cloud Run

`/data` is the Cloud Storage bucket, so enrolled voiceprints survive restarts and redeploys. `--max-instances=1` keeps a single copy of the speaker registry; two instances writing the same JSON file would overwrite each other.

```bash
gcloud run deploy $SERVICE \
  --image=$IMAGE --region=$REGION \
  --port=8001 --cpu=2 --memory=4Gi \
  --min-instances=0 --max-instances=1 --concurrency=10 \
  --timeout=300 --cpu-boost --execution-environment=gen2 \
  --add-volume=name=data,type=cloud-storage,bucket=$BUCKET,mount-options="uid=10001;gid=10001" \
  --add-volume-mount=volume=data,mount-path=/data \
  --no-allow-unauthenticated
```

### 5. Test

```bash
gcloud run services proxy $SERVICE --region=$REGION --port=8001
```

Then open `http://localhost:8001/demo`, or in another terminal:

```bash
curl http://localhost:8001/health
curl -X POST -F "file=@sample.wav" http://localhost:8001/age-gender/predict
```

The service is private by default. To open it to anyone with the URL, which is not advised for real voice data, redeploy with `--allow-unauthenticated` and use the `https://...run.app` URL that `gcloud run services describe $SERVICE --region=$REGION --format='value(status.url)'` prints.

`--min-instances=0` scales to zero when idle, so the first request after a pause takes about 20-40 s while the models load. Set `--min-instances=1` to keep one instance warm, at extra cost.

### Update after a code change (on the VM)

```bash
IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/voice-iq-mam:v2
docker build -t $IMAGE . && docker push $IMAGE
gcloud run deploy $SERVICE --image=$IMAGE --region=$REGION
```

Delete the build VM when you are not building: `gcloud compute instances delete $VM --zone=$ZONE`.

## Run locally with Docker

```bash
docker build -t voice-iq-mam .
docker run --rm -p 8001:8001 -v voice-iq-data:/data voice-iq-mam
```

Open `http://localhost:8001/demo` for the guided UI or `http://localhost:8001/docs` for the API.

## Test the complete flow

Open `http://localhost:8001/demo` and enter a speaker/customer ID.

1. For a new speaker, record three enrollment clips. The UI enrolls each clip immediately.
2. After enrollment, record a separate biometric-test clip. For an existing speaker, proceed directly to this test.
3. Review the 1:1 verification and 1:N identification results.
4. Select any enrollment or test recordings still available in the current session, then click **Profile selected**. Each selected clip is sent to `/age-gender/predict` and gets an individual age/gender result.

API calls, with recordings at least 3 seconds long:

```bash
curl -X POST \
  -F "files=@enroll-1.wav" -F "files=@enroll-2.wav" -F "files=@enroll-3.wav" \
  http://localhost:8001/biometrics/speakers/alex/enroll

curl -X POST -F "speaker_id=alex" -F "file=@biometric-test.wav" http://localhost:8001/biometrics/verify
curl -X POST -F "file=@biometric-test.wav" http://localhost:8001/biometrics/identify
curl -X POST -F "file=@biometric-test.wav" http://localhost:8001/age-gender/predict
```

Example `/age-gender/predict` response:

```json
{
  "status": "success",
  "filename": "biometric-test.wav",
  "audio_duration_seconds": 6.57,
  "age_group": "twenties",
  "age_bucket": "20-30",
  "age_confidence": 0.81,
  "age_probabilities": {"teens": 0.05, "twenties": 0.81, "thirties": 0.1, "fourties": 0.02, "fifties": 0.01, "sixties": 0.01},
  "gender": "Male",
  "gender_confidence": 0.96,
  "gender_probabilities": {"female": 0.04, "male": 0.96},
  "gender_age": {"label": "male-twenties", "confidence": 0.7},
  "processing_time_seconds": 0.21
}
```

MaM predicts age **groups**, not years. There is no `estimated_age` field as there is in the VoxProfile build. Clips longer than 5 s are split into 5 s windows; each window becomes one spectrogram, and the class probabilities are averaged.

The speaker registry stores voice embeddings, not recordings. Session audio is not persisted by the server. The `/data` volume stores the registry across container restarts.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Service status |
| GET | `/biometrics/health` | Biometrics engine status |
| GET | `/biometrics/speakers` | List enrolled speakers |
| POST | `/biometrics/speakers/{speaker_id}/enroll` | Enroll several recordings |
| POST | `/biometrics/speakers/{speaker_id}/enroll-one` | Enroll one recording |
| DELETE | `/biometrics/speakers/{speaker_id}` | Delete a voiceprint |
| POST | `/biometrics/verify` | 1:1 speaker verification |
| POST | `/biometrics/identify` | 1:N speaker identification |
| POST | `/biometrics/call` | Enrollment/authentication call flow |
| POST | `/biometrics/compare` | Compare two recordings |
| GET | `/age-gender/health` | MaM model status and loaded heads |
| POST | `/age-gender/predict` | Age and gender prediction |
| WS | `/age-gender/ws` | Age and gender prediction over WebSocket |

## Configuration

| Variable | Default (Docker) | Meaning |
| --- | --- | --- |
| `MODEL_ROOT` | `/models` | Folder with `age/`, `gender/`, `gender_age/` weights |
| `LOAD_TASKS` | `age,gender,gender_age` | Which MaM heads to load |
| `VD_REGISTRY` | `/data/registry.json` | Speaker registry file |
| `VD_LIB`, `VD_MODEL` | built into the image | Speaker engine and model |
| `VD_THRESHOLD`, `VD_*` | see `biometrics/config.py` | Biometrics thresholds and limits |
| `LOG_LEVEL` | `INFO` | Log level |

## Run tests

```bash
python -m unittest discover tests
```

This demo has no authentication. Put it behind an authenticated HTTPS gateway before exposing it publicly; voiceprints and profiling results are sensitive data.
