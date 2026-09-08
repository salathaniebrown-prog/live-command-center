# Eagle Eyes Mobile

Recovered from the original `eagle-eyes-mobile` repository into the unified
Eagle Eyes repository.

## Live backend

By default the app uses:

```text
https://live-command-center-production-31ed.up.railway.app
```

To point a development build at another real Eagle Eyes server:

```bash
EXPO_PUBLIC_EAGLE_EYES_BASE_URL=https://your-host.example npx expo start
```

## Run locally

```bash
cd clients/mobile
npm install
npx expo start
```

## Build an APK

The repository includes `.github/workflows/eagle-eyes-android-apk.yml`. It
prebuilds the Expo Android project and runs Gradle `assembleRelease`, then
uploads the installable APK as the `Eagle-Eyes-Android-Standalone` workflow
artifact.

For local recovery builds:

```bash
cd clients/mobile
npm run check
npm run bundle:android
npx expo prebuild --platform android --non-interactive
cd android
./gradlew assembleRelease
```

The production EAS configuration and project ID from the original mobile
repository are preserved in `app.json` and `eas.json`.
