# Logmaxxing Privacy Policy

Effective date: June 23, 2026

This Privacy Policy explains how Logmaxxing ("Logmaxxing", "we", "us", or "our") collects, uses, stores, and protects information when you use the mobile application listed on Google Play as "Logmaxxing - Workout Log" and any related website or backend service that supports the app.

- Website: https://fitness-tracker-39bca.web.app
- Contact email: me@kunaaldesai.com
- Developer: Kunaal Desai

## 1. What Logmaxxing Does

Logmaxxing is a workout logging app. It lets users sign in, create an account, log exercises and sets, track body weight and profile metrics, view workout records, and use rest timer notifications.

## 2. Information We Collect

### Account and sign-in information

When you sign in, Logmaxxing uses Firebase Authentication and Google sign-in. We may receive and store:

- Your Firebase user ID.
- Your email address.
- Your display name.
- Your profile photo URL, if provided by your sign-in provider.
- Authentication metadata needed to keep you signed in.

### Workout and fitness information you enter

Logmaxxing stores the workout and fitness information you choose to enter, including:

- Exercise names.
- Exercise categories and movement types.
- Workout dates.
- Sets, reps, weights, RPE, duration, distance, side, and notes.
- Workout day summaries and rollups.
- Personal record calculations and exercise history.
- Body weight entries and notes.
- Profile inputs such as first name, last name, date of birth, sex used for BMR formulas, height, weight, target weight, body fat percentage, activity level, BMR formula, and calorie goal settings.

### App settings stored on your device

The app may store local settings on your device, including:

- Theme preference.
- Workout timer settings and timer state.
- Firebase authentication session data.

On supported mobile devices, authentication session data is stored using secure device storage. Some non-sensitive preferences may be stored using local app storage.

### Notification permission and timer notifications

Logmaxxing may ask for notification permission so it can show rest timer alerts. Rest timer notifications are scheduled on your device and are used for app functionality. They are not used for advertising or tracking.

### Technical and security information

When you use the backend API, we may process technical information needed to operate and secure the service, including:

- Firebase ID tokens sent with API requests.
- IP address or network metadata visible to the hosting and Cloud Functions infrastructure.
- Request path, timestamps, and error logs.
- Rate-limit counters used to prevent abuse.

## 3. Information We Do Not Collect

Based on the current app codebase, Logmaxxing does not collect:

- Precise location.
- Contacts.
- Photos, videos, or files from your device.
- Camera or microphone data.
- Payment card information.
- Advertising identifiers for ad targeting.

Logmaxxing does not currently include third-party ads or sell personal information.

## 4. How We Use Information

We use information to:

- Create and maintain your account.
- Authenticate your requests.
- Store and sync your workout log.
- Show workout history, analytics, records, charts, and profile metrics.
- Calculate fitness metrics such as BMI, BMR, TDEE, workout volume, streaks, and personal records.
- Send local rest timer notifications when you enable them.
- Protect the service from misuse, abuse, excessive traffic, and unauthorized access.
- Debug, maintain, and improve the app and backend.
- Comply with legal obligations and enforce applicable terms or policies.

## 5. Legal Bases for Processing

Where applicable law requires a legal basis, we process your information under one or more of the following bases:

- Performance of a contract: to provide the app features you request.
- Consent: for optional permissions such as notifications or where otherwise required.
- Legitimate interests: to secure, maintain, debug, and improve the app.
- Legal obligations: to comply with applicable law, valid requests, and platform requirements.

## 6. How Information Is Stored

Logmaxxing uses Google Firebase and Google Cloud services, including Firebase Authentication, Cloud Firestore, Firebase Hosting, and Cloud Functions.

Your app data is stored in Cloud Firestore under your authenticated user ID. Direct client access to Firestore is denied by the app's security rules; the mobile app communicates with the backend API, and the backend verifies Firebase ID tokens before accessing user data.

The backend may also use Google Cloud BigQuery exports for operational analytics, reporting, backup, debugging, or service improvement. These exports may include workout days, exercise entries, weight entries, exercise definitions, and analytics event data if enabled.

## 7. How We Share Information

We do not sell your personal information.

We may share or process information with:

- Google Firebase and Google Cloud, which provide authentication, database, hosting, backend, logging, and infrastructure services.
- Google sign-in services, when you choose to sign in with Google.
- Service providers or contractors who help operate the app, only as needed and under appropriate confidentiality and security obligations.
- Law enforcement, regulators, courts, or other parties when required by law or to protect rights, safety, and security.
- A successor organization if Logmaxxing is involved in a merger, acquisition, reorganization, or asset transfer.

## 8. Security

We use reasonable technical and organizational measures to protect information, including:

- HTTPS for API traffic.
- Firebase ID token verification on backend requests.
- Server-side user scoping so users can access only their own workout and profile data.
- Firestore rules that deny direct client reads and writes.
- Secure device storage for authentication persistence where supported.
- Server-side validation of request bodies and limits on payload sizes such as set counts, copy counts, and page sizes.
- Server-side rate limiting for API requests.

No method of transmission or storage is perfectly secure, and we cannot guarantee absolute security.

## 9. Data Retention

We keep your account and workout data for as long as your account is active or as needed to provide the service. We may keep limited records for backup, security, legal compliance, dispute resolution, or legitimate business purposes.

You can delete your account in the app from the gear icon settings dialog. In-app deletion permanently deletes your Firebase Authentication account and your Firestore account data, including workout logs, weight logs, profile details, exercise definitions, workout-day summaries, and exercise records.

You can also request deletion from the web deletion page at https://fitness-tracker-39bca.web.app/delete-account.html. If you request deletion by email, we may need to verify that you control the account before completing the request.

We may keep limited records for backup, security, legal compliance, dispute resolution, or legitimate business purposes.

## 10. Your Choices and Rights

Depending on where you live, you may have rights to:

- Access personal information we hold about you.
- Correct inaccurate information.
- Delete your account or personal information.
- Export your data.
- Object to or restrict certain processing.
- Withdraw consent where processing is based on consent.

To make a request, contact us at kunaaldesai13@gmail.com or use the deletion request page at https://fitness-tracker-39bca.web.app/delete-account.html. We may need to verify your identity before completing the request.

You can also control some information directly in the app, including workout entries, profile details, weight entries, timer settings, and notification permission through your device settings.

## 11. Children's Privacy

Logmaxxing is not intended for children under 13 years old, and we do not knowingly collect personal information from children under 13. If you believe a child has provided personal information, contact us and we will take appropriate steps to delete it.

If your jurisdiction requires a higher minimum age for digital services, you must meet that age requirement to use Logmaxxing.

## 12. International Data Transfers

The services that support Logmaxxing may process and store information in the United States or other countries where Google Cloud or our service providers operate. These countries may have data protection laws that differ from those in your location.

## 13. Third-Party Services

Logmaxxing relies on third-party services, including:

- Google Firebase Authentication.
- Google Cloud Firestore.
- Google Cloud Functions.
- Firebase Hosting.
- Google sign-in.
- Google Cloud BigQuery, if export or analytics workflows are enabled.

Their processing is governed by their own terms and privacy documentation.

## 14. Google Play Data Safety Summary

For Google Play's Data safety form, the current codebase indicates the following high-level disclosures:

- Data collected: name, email address, user ID, profile photo URL if provided, fitness and health-related workout/body-metric data, app activity related to workout logs and analytics, and basic diagnostics/security logs.
- Data sharing: data is processed by Google/Firebase/Google Cloud service providers to provide app functionality. No sale of personal information and no third-party advertising use is currently implemented.
- Data security: data is transmitted over HTTPS. Account data is protected by Firebase Authentication. Direct Firestore client access is denied.
- Data deletion: users can delete their account in the app from the gear icon settings dialog. Users can also request account deletion at https://fitness-tracker-39bca.web.app/delete-account.html or by contacting me@kunaaldesai.com.

This summary is provided to help complete the Play Console form, but you should confirm each answer against your deployed production configuration before submission.

## 15. Changes to This Policy

We may update this Privacy Policy from time to time. When we make changes, we will update the effective date above. Material changes may also be announced in the app, on the website, or by other reasonable means.

## 16. Contact

For privacy questions or requests, contact:

Kunaal Desai  
https://fitness-tracker-39bca.web.app  
me@kunaaldesai.com
