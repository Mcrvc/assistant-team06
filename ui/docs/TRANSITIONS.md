# Prototype transition map

Read from Figma Page 1 on 2026-10-27: 16 application screens, 62 click connections. The Moodboard is design reference only.

Each application frame has its own HTML page. Layer names below are replaced with visible button text where the Figma layer name differs.

| Screen | Control | Destination | Figma transition |
| --- | --- | --- | --- |
| system-feedback.html | Dashboard | dashboard.html | Instant |
| system-feedback.html | Avatar | profile.html | Instant |
| system-feedback.html | Submit button | thank-you.html | SLIDE_IN LEFT, 300 ms |
| thank-you.html | Dashboard | dashboard.html | Instant |
| thank-you.html | Avatar | profile.html | Instant |
| thank-you.html | Back to home | dashboard.html | SMART_ANIMATE, 300 ms |
| report.html | Dashboard | dashboard.html | Instant |
| report.html | Avatar | profile.html | Instant |
| report.html | Home | dashboard.html | SMART_ANIMATE, 300 ms |
| done-interview.html | Dashboard | dashboard.html | Instant |
| done-interview.html | Avatar | profile.html | Instant |
| done-interview.html | View Report | report.html | SMART_ANIMATE, 300 ms |
| interview-3.html | Dashboard | dashboard.html | Instant |
| interview-3.html | Avatar | profile.html | Instant |
| interview-3.html | Finalize Interview | done-interview.html | PUSH LEFT, 300 ms |
| interview-3.html | Prev | interview-2.html | PUSH RIGHT, 300 ms |
| interview-3.html | Quit | interview-interrupt.html | PUSH TOP, 300 ms |
| interview-2.html | Dashboard | dashboard.html | Instant |
| interview-2.html | Avatar | profile.html | Instant |
| interview-2.html | Next | interview-3.html | PUSH LEFT, 300 ms |
| interview-2.html | Prev | interview-1.html | PUSH RIGHT, 300 ms |
| interview-2.html | Quit | interview-interrupt.html | PUSH TOP, 300 ms |
| interview-interrupt.html | Dashboard | dashboard.html | Instant |
| interview-interrupt.html | Avatar | profile.html | Instant |
| interview-interrupt.html | Back | dashboard.html | SLIDE_IN LEFT, 300 ms |
| interview-1.html | Dashboard | dashboard.html | Instant |
| interview-1.html | Avatar | profile.html | Instant |
| interview-1.html | Next | interview-2.html | PUSH LEFT, 300 ms |
| interview-1.html | Quit | interview-interrupt.html | PUSH TOP, 300 ms |
| cv.html | Dashboard | dashboard.html | Instant |
| cv.html | Avatar | profile.html | Instant |
| cv.html | Continue | interview-1.html | Instant |
| cv.html | Input Job Profile | job-profile.html | SLIDE_IN TOP, 300 ms |
| job-profile.html | Dashboard | dashboard.html | Instant |
| job-profile.html | Avatar | profile.html | Instant |
| job-profile.html | Input CV | cv.html | SLIDE_IN BOTTOM, 300 ms |
| job-profile.html | Continue | interview-1.html | SLIDE_IN LEFT, 300 ms |
| storage.html | Dashboard | dashboard.html | Instant |
| storage.html | Continue | interview-1.html | Instant |
| storage.html | View report | report.html | Instant |
| storage.html | View report | report.html | Instant |
| storage.html | View report | report.html | Instant |
| storage.html | Back to home | dashboard.html | SMART_ANIMATE, 300 ms |
| storage.html | Avatar | profile.html | Instant |
| profile.html | Dashboard | dashboard.html | Instant |
| profile.html | Avatar | profile.html | Instant |
| profile.html | Avatar | profile.html | Instant |
| profile.html | Save button | dashboard.html | SMART_ANIMATE, 300 ms |
| profile.html | Sign out button | sign-in.html | DISSOLVE, 300 ms |
| dashboard.html | Avatar | profile.html | Instant |
| dashboard.html | Create a new interview | job-profile.html | SMART_ANIMATE, 300 ms |
| dashboard.html | View interview | storage.html | SMART_ANIMATE, 300 ms |
| dashboard.html | Rate our assistant | system-feedback.html | SMART_ANIMATE, 300 ms |
| sign-up.html | Sign up button | dashboard.html | DISSOLVE, 300 ms |
| sign-up.html | Already have an account?, Sign in | sign-in.html | PUSH RIGHT, 300 ms |
| sign-in.html | Sign in button | dashboard.html | DISSOLVE, 300 ms |
| sign-in.html | Dont have an account?, Sign up | sign-up.html | PUSH LEFT, 300 ms |

Implementation notes:

- The table records the original Figma destinations and animation settings. The HTML uses ordinary page links and a short entry fade; the original PUSH/SMART_ANIMATE effects await a later visual review.
- Header avatars link to Profile. The large avatar in Profile also links to Profile, matching the source connections. Both use the complete user-exported Avatar.svg.
- The interrupted-interview page presents a modal. Its background navigation is inactive while the saved dialog is open.
- Storage Continue opens interview-1.html as specified in Figma; all previously entered answers remain saved.
- Per the user's confirmed PoC scope, controls without behavior in the source Figma remain non-interactive. Delete and Microphone stay disabled; no new behavior is required.
- New form states implement the approved CV, job profile and profile-editing changes.

