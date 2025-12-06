**📌How to Create Google OAuth Credentials JSON File**



This guide explains how to generate the credentials.json file required for apps using Google APIs (YouTube, Gmail, Drive, etc.)



----------------------------------------------------------------------------



###### **✅ Step 1 — Open Google Cloud Console**



Go to the Google Cloud console:https://console.cloud.google.com/

Login using your Google account.



----------------------------------------------------------------------------



###### **✅ Step 2 — Create a New Project**



1.Click Select Project on the top bar.

2.Click New Project.

3.Enter a Project Name (Example: BotFather).

4.Click Create.



**📌 Wait for the new project to finish creating and select it if not auto-selected.**

------------------------------------------------------------------------------



###### **✅ Step 3 — Enable API(s)**



1.Go to:

&nbsp;       **Navigation Menu → APIs \& Services → Library**

2.Search and enable the API(s) you need:

&nbsp;      - YouTube Data API v3 (for YouTube bot).

&nbsp;      - Google Drive API (for file apps).

&nbsp;      - Gmail API (for email automation).

3.Click Enable



------------------------------------------------------------------------------



###### **✅ Step 4 — Configure OAuth Consent Screen**



1.Go to:

&nbsp;      **APIs \& Services → OAuth consent screen**

2.Select External.

3.Fill required details:

&nbsp;      - App name (any)

&nbsp;      - Email (required)

4.Save \& Continue through all steps.



**⚠️ In Production apps, additional verification may be required.**

-----------------------------------------------------------------------------

✅ Step 5 — Create OAuth Client ID Credentials

1.Go to:
       
       APIs & Services → Credentials
2.Click 'Create Credentials'.

3.Select OAuth 'Client ID'.

4.Application type → Desktop App.

5.Enter any name → Click Create.

------------------------------------------------------------------------------

🎉 Step 6 — Download Credentials JSON

✔ Click Download.
