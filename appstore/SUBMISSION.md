# Figure Shelf: App Store submission sheet

Everything App Store Connect asks for, in the order it asks. Texts for the listing are in `listing.md`.

## 1. Upload the build (Xcode)

**Use the regular Xcode project, not the .swiftpm App Playground.** App Playground builds stamp the binary
with the deployment target (iOS 18.0) as its SDK version, and App Store Connect rejects them
("built with the iOS 18.0 SDK"). The Xcode project uses the same code and assets and records the real SDK (iOS 27).

1. Open `FigureShelf-Xcode/FigureShelf.xcodeproj` in Xcode 27 (not `FigureShelf.swiftpm`, and not Swift Playgrounds).
   A ready archive, "Figure Shelf 1.0 (2)", is already in Xcode's Organizer (Window > Organizer > Archives).
   To make a new one: choose **Any iOS Device (arm64)**, then **Product > Archive**.
2. In the Organizer, select **Figure Shelf 1.0 (2)** and click **Distribute App > App Store Connect > Upload**.
   Keep "Automatically manage signing" and "Upload symbols" on.
3. The build shows up in App Store Connect (TestFlight tab) after 5 to 30 minutes of processing.
   Encryption is already answered in the app (ITSAppUsesNonExemptEncryption = NO), so there's no compliance question.
4. For later builds, raise `CURRENT_PROJECT_VERSION` in `FigureShelf-Xcode/project.yml` (3, 4, …), then run
   `xcodegen` in that folder (it also picks up new Swift files). Keep developing in the .swiftpm as usual.

## 2. New app record (App Store Connect > Apps > + > New App)

| Field | Value |
|---|---|
| Platforms | iOS |
| Name | Figure Shelf |
| Primary language | English (U.S.) |
| Bundle ID | app.figureshelf.FigureShelf |
| SKU | FIGURESHELF-001 (any unique text; never shown to users) |
| User access | Full Access |

If the bundle ID isn't in the list, the first upload from Xcode registers it. Or add it under Certificates, Identifiers & Profiles > Identifiers.

## 3. App Information

| Field | Value |
|---|---|
| Subtitle | 3D animals & dinos in AR |
| Primary category | Entertainment |
| Secondary category | Education (optional) |
| Content rights | "No, it does not contain, show, or access third-party content". The 3D models were made for this app with Meshy on a paid plan (you own them), and the sounds were made for the app. |
| Age rating | Fill in the questionnaire as in section 4. Expected result: 4+ |
| Made for Kids / Kids Category | Not selected (Entertainment) |
| License agreement | Apple's standard EULA (leave as is) |

## 4. Age rating questionnaire

Answer **None** or **No** to everything:

- Violence (cartoon, realistic, graphic): None
- Sexual content, nudity: None
- Profanity or crude humor: None
- Alcohol, tobacco, drugs: None
- Mature or suggestive themes, horror or fear themes: None. The dinosaurs are calm and not aggressive.
- Medical or treatment information: None
- Gambling, simulated gambling, contests: None / No
- Unrestricted web access: No. The only links are the app's own privacy and support pages, opened behind a 3-second hold.
- User-generated content, messaging, chat: No
- Advertising: No
- Parental controls or age assurance: No (not needed)

## 5. Pricing and Availability

| Field | Value |
|---|---|
| Price | Free (Tier 0), or your choice |
| In-app purchases | None |
| Availability | All countries and regions (or your choice) |
| Pre-order | No |

**EU (Digital Services Act):** App Store Connect asks whether you are a **trader** (you sell or earn from apps as a business) or a **non-trader**. A trader has their contact details (address, phone, email) shown on the EU App Store page. This is your decision. A free hobby app is usually "non-trader". If you choose trader, Apple verifies your address and phone.

## 6. App Privacy

| Field | Value |
|---|---|
| Privacy Policy URL | https://fplotnikov.github.io/figureshelf-web/privacy.html |
| Data collection | No, we do not collect data from this app |
| Tracking | No |

The privacy manifest (PrivacyInfo.xcprivacy) in the build matches: no tracking, no collected data, UserDefaults reason CA92.1.

## 7. Version 1.0 page (iOS App > 1.0 Prepare for Submission)

| Field | Value |
|---|---|
| Promotional text | from `listing.md` (121/170) |
| Description | from `listing.md` |
| Keywords | dinosaur,animals,3D,AR,toy,robot,figures,dress up,augmented reality,trex,zoo,calm,family,models (95/100) |
| Support URL | https://fplotnikov.github.io/figureshelf-web/support.html |
| Marketing URL (optional) | https://fplotnikov.github.io/figureshelf-web/ |
| Version | 1.0 |
| Copyright | 2026 Fedir Plotnikov |
| Build | pick the uploaded build 1.0 (2) |
| App icon | comes from the build (1024 px, no transparency) |

### Screenshots (upload in this order)

- **iPhone 6.9" display** (1320 x 2868): `appstore/screenshots/iphone-1-picker.png`, `iphone-2-dinosaur.png`,
  `iphone-3-accessories.png`, `iphone-4-action-wave.png`, `iphone-5-robot.png`.
  Apple scales these down for the smaller iPhone sizes.
- **iPad 13" display** (2048 x 2732): `appstore/screenshots/ipad-1-picker.png` … `ipad-5-robot.png`.

### App Review Information

| Field | Value |
|---|---|
| Sign-in required | No |
| Contact first / last name | Fedir Plotnikov |
| Contact phone | YOUR PHONE (with country code; only Apple sees it) |
| Contact email | support@brightsteps.app |
| Notes | see below |
| Attachment | none needed |

Notes for the reviewer:

> No sign-in is needed. Every figure is unlocked. To try augmented reality, tap "See in my room" on an AR-capable device and point the camera at the floor. Swipe the bottom menu down to view a figure full screen, and pinch to zoom. The parents' info (privacy and support links) opens when you press and hold the "i" button for 3 seconds, so young children don't open Safari by accident. The app collects no data and makes no network requests.

### Version release

Choose **Manually release this version** if you want to press the button yourself after approval, or
**Automatically release** to go live as soon as it's approved.

## 8. Optional: Accessibility (App Store Connect > Accessibility)

Honest answers, if you fill this in:
- Larger text: partly (the system sizes are used in most places)
- Dark interface: No (the app stays light on purpose)
- Differentiate without color, sufficient contrast, reduced motion: leave unchecked unless you test them
- VoiceOver: buttons have labels, but the 3D view isn't described. Leave unchecked.

## 9. Submit

**Add for Review > Submit to App Review.** A review usually takes 1 to 3 days. You'll get an email when the
status changes.

## Facts about the build

- Bundle ID app.figureshelf.FigureShelf, version 1.0, build 2, team B6LBNVRNQ4, built with Xcode 27 / iOS 27 SDK
- iOS 18.0 or later, iPhone (portrait) and iPad (all orientations)
- Download about 172 MB, installed about 209 MB
- Camera use text: "The camera lets your animal appear in your room."
- AR is optional: devices without AR still install, and the room button hides
- No network use, no accounts, no ads, no analytics, no purchases
- For the next build, raise `bundleVersion` in Package.swift (2, 3, …). For a new release, raise `displayVersion`.
