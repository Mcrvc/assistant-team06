# LOCAL-03: Visible answer validation and explicit exit choices

Requested by Tran Bao Anh after manual testing. Keep local commit checkpoints
after each completed change; no push or cloud changes.

- [x] Show missing-answer validation next to the answer field, with a strong
  visual treatment, accessible message, invalid state and focus on the field.
- [ ] Ask before leaving: Save & exit, Leave without saving, Keep answering.
  Do not auto-save drafts while typing or save before displaying the question.
- [ ] Discard only unsubmitted changes, preserve answers already submitted by
  Next, and keep the interview open if saving fails. Support sign-out and Back.
- [ ] Cover save/discard/cancel/error paths with browser tests; update docs.

Browser reload/tab close uses the browser's native unsaved-changes prompt;
custom three-choice dialogs only apply to in-app navigation and intercepted Back.
