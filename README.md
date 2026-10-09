# url-to-apk

Paste a website address, get an Android app. Built for free by GitHub Actions.

**Use it:** https://luishae07.github.io/url-to-apk/

## How it works

1. The page opens a pre-filled GitHub issue ("Build: example.com [abc123]"). You press *Submit new issue*.
2. The workflow `.github/workflows/build.yml` starts on that issue. `tools/prepare.py` checks the address (https only, public websites only), reads the site's name, theme colour and icon, and fills them into the Android project in `template/`.
3. Gradle builds the APK. It is signed with the standard debug key, so it installs straight away but is not for the Play Store.
4. The APK is attached to a release (`apk-issue-<number>`), the bot comments the link on the issue and closes it. The page finds the issue again and shows the download.

You can also start a build by hand from the *Actions* tab ("Run workflow"), or with the API:

```
curl -X POST -H "Authorization: Bearer <token>" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/Luishae07/url-to-apk/dispatches \
  -d '{"event_type":"build-apk","client_payload":{"url":"https://example.com","name":"Example","location":"no"}}'
```

## What the app does

A full-screen web view of the site. Links to other sites open in the normal browser. https only. Optionally it may ask for the phone's location. Nothing else is added: no tracking, no extra permissions beyond the internet.

## Limits

- Debug-signed: updates built later can be refused by Android until the old app is removed.
- The site must be a public https website that answers automatic visits.
- Please only wrap sites you own or may use this way.
