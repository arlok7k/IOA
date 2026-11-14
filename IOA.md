PROJECT IMPLEMENTATION SPECIFICATION
IOA — Institute Outreach Automation
Cloud Development + Local Windows Execution
WhatsApp Outreach & Telegram Approval Management System
1. PROJECT OVERVIEW

Build a professional, reliable Windows desktop application named:

IOA — Institute Outreach Automation

The project must be developed entirely within the AI agent's cloud development environment, then delivered as a complete Windows application that the user can download, install, and run locally.

The final application must operate locally on the user's Windows computer without requiring a permanent cloud server or cloud database.

The system automates personalized business outreach to training institutes and educational centers using WhatsApp Web, with individual approval and remote control through a Telegram Bot.

The application uses:

An Excel workbook containing institute information.
A TXT file containing a predefined message template.
WhatsApp Web through one specific existing Chrome profile.
A Telegram Bot for remote approvals, scheduling, monitoring, and campaign control.
SQLite for persistent local application state.
1.1 DEVELOPMENT AND EXECUTION ARCHITECTURE

CRITICAL ARCHITECTURAL REQUIREMENT:

Development and runtime execution must be separated.

Cloud Development Environment

The AI development agent must:

Create the complete Python project.
Implement all application modules.
Write and maintain the source code.
Install development dependencies in its environment.
Run automated tests.
Identify and fix implementation errors.
Perform static analysis and code-quality checks.
Prepare Windows-compatible application builds.
Generate the final project deliverables.
Produce installation and usage documentation.

The development agent must not require direct access to the user's local Windows computer during ordinary development.

The cloud environment does not contain the user's existing Chrome Profile 40 or authenticated WhatsApp session.

Never assume that a local Windows file path is accessible from the cloud environment.

Local Windows Runtime Environment

The final application must run on the user's Windows computer.

Local runtime responsibilities include:

Accessing the specified Excel and TXT files.
Accessing the existing Chrome Profile 40.
Connecting to WhatsApp Web.
Sending approved messages.
Running the local scheduler.
Maintaining SQLite data.
Running the Telegram Bot integration.
Maintaining campaign state and activity logs.
Final Delivery

Deliver:

Complete Python source code.
Windows executable application.
Installation package or straightforward installation procedure.
All required dependencies.
Configuration templates.
Documentation.
Automated test results.
Windows build verification results.

The user must be able to download the completed application from the cloud development environment and install it on their Windows computer.

Do not require the user to manually recreate project files or write application code.

2. INPUT FILES AND DATA MANAGEMENT
2.1 Input Directory

The initial input directory on the user's Windows computer is:

C:\Users\USERW\Desktop\contect - Copy

This is a directory, not an individual file.

The application must:

Inspect this directory at local runtime.
Identify available Excel workbooks and TXT message templates.
Support common Excel extensions, particularly .xlsx.
Avoid assuming filenames.
Display discovered files in the application interface.
Allow the user to select or change the files.
Display clear errors if required files are missing or ambiguous.

The application must not attempt to access this Windows directory from the cloud development environment.

Do not rename, move, overwrite, or unnecessarily modify original input files.

2.2 Excel Data Structure

The Excel workbook contains information such as:

Field	Description
Institute Name	Institute or training center name
Phone Number	WhatsApp contact number
Address	Institute location
Contact Status	Whether communication has occurred
Notes	Additional information

Column headers may be in Arabic.

Requirements:

Do not hardcode column positions.
Do not assume exact header names.
Implement flexible column detection.
Provide a column-mapping interface.
Support Arabic and English column names.
Preserve all existing columns, rows, formatting, and unrelated information when updating the workbook.
2.3 Contact Status Management

Support these internal statuses:

Pending
Awaiting Approval
Approved
Scheduled
Sending
Sent
Failed
Skipped
Invalid Number
Uncertain

Interpret existing Arabic status values appropriately.

A contact already marked as contacted must never be automatically selected again.

After a confirmed successful send:

Update the contact status to تم التواصل.
Record the exact sending date and time.
Append a descriptive note when necessary.

If sending fails:

Do not mark the contact as contacted.
Record the failure reason.
Preserve the contact for later review.

If the sending outcome is uncertain:

Do not mark the contact as contacted.
Do not automatically retry.
Require conversation verification or manual review.

Create a backup of the original workbook before the first modification.

Use safe file-writing procedures and preserve the original workbook whenever possible.

3. MESSAGE TEMPLATE ENGINE

Read message content from the TXT file.

The message must remain unchanged except for replacing the institute-name placeholder.

Preferred configurable placeholder:

{{institute_name}}

Example:

Original template:

"السلام عليكم ورحمة الله وبركاته،

يسعدنا التواصل مع {{institute_name}} لعرض فرصة تعاون في مجال التدريب التقني والأمن السيبراني..."

Generated message:

"السلام عليكم ورحمة الله وبركاته،

يسعدنا التواصل مع معهد المستقبل لعرض فرصة تعاون في مجال التدريب التقني والأمن السيبراني..."

Requirements:

Preserve Arabic text.
Preserve UTF-8 encoding.
Preserve line breaks and punctuation.
Replace only the intended placeholder.
Never rewrite or paraphrase the original message.
Display a preview before sending.
Detect missing or incorrect placeholders.
Never send an empty or malformed message.
Support Arabic institute names correctly.
4. WHATSAPP WEB AUTOMATION
4.1 FIXED CHROME PROFILE MANAGEMENT

CRITICAL REQUIREMENT: USE ONLY PROFILE 40.

The user's computer contains multiple Chrome profiles.

The application must exclusively use the following existing profile:

Chrome Profile Name:

Profile 40

Exact profile path:

C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40

The profile contains the WhatsApp account that must be used for all campaign operations.

The application must NOT:

Discover alternative Chrome profiles.
Select alternative profiles.
Offer a profile-selection interface.
Automatically switch profiles.
Create another profile as a fallback.
Copy authentication cookies.
Extract passwords or session secrets.
Interfere with other Chrome profiles.
Terminate unrelated Chrome processes.

Fixed configuration:

python
CHROME_USER_DATA_DIR = (
    r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data"
)

CHROME_PROFILE_DIRECTORY = "Profile 40"

CHROME_PROFILE_PATH = (
    r"C:\Users\USERW\AppData\Local\Google/Chrome/User Data/Profile 40"
)


Use the correct configuration:

User data directory: C:\Users\USERW\AppData\Local\Google\Chrome\User Data
Profile directory: Profile 40

Never incorrectly pass the profile directory as the Chrome user-data directory.

Profile Safety

Requirements:

Verify that the profile directory exists.
Stop execution if the directory does not exist.
Detect profile-lock conflicts.
Never launch multiple browser instances against the same user-data directory simultaneously.
Never terminate Chrome processes to force access.
Explain conflicts and offer a safe recovery procedure.
Prefer a dedicated IOA-controlled Chrome session using the existing Profile 40.
If attaching to an existing browser session is necessary, use a supported and explicitly configured mechanism.
Do not assume remote debugging can be enabled on an already-running Chrome process without appropriate configuration.

If the profile is locked, explain the situation and instruct the user how to safely close the relevant Chrome session before retrying.

Never silently use another profile.

Cloud Development Restriction

The cloud development agent must not attempt to launch the user's Profile 40.

It must implement the browser integration and test it using:

Mock browser interfaces.
Simulated profile paths.
Isolated test environments.
Test doubles for WhatsApp interactions.

Actual authentication and browser integration must be verified later on the user's Windows computer.

4.2 WHATSAPP CONNECTION

Implement a WhatsApp connection manager.

The application must:

Open WhatsApp Web using Profile 40.
Verify account authentication.
Detect QR-code login requirements.
Detect disconnected or expired sessions.
Stop execution if authentication is unavailable.
Display connection state in the dashboard.
Never use another Chrome profile.

Dashboard information:

WhatsApp Account: Profile 40

Profile Path:

C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40

4.3 SENDING WORKFLOW

For each approved institute:

Retrieve institute name and phone number.
Validate and normalize the phone number.
Generate the personalized message.
Open the correct WhatsApp conversation.
Verify the intended conversation.
Populate the message.
Confirm that a valid individual approval exists.
Send the message.
Verify the outgoing message appears in the conversation.
Record the result.
Update Excel only after successful confirmation.

Do not treat opening a chat or populating the message box as a successful send.

Distinguish between:

Submitted successfully in WhatsApp.
Delivered, if reliable delivery evidence is available.
Failed.
Uncertain.

Never automatically retry uncertain sends without checking the conversation first.

Avoid duplicate messages.

Respect WhatsApp's applicable policies, recipient preferences, and applicable rate limits.

Do not implement anti-abuse evasion, artificial randomization, or mechanisms designed to bypass platform restrictions.

5. TELEGRAM BOT — REMOTE CONTROL

Telegram is the remote-control interface for the locally running IOA application.

The bot must communicate with the local application through an authenticated Telegram API connection.

A permanent cloud server is not required.

The local application can use polling or another appropriate Telegram connection method.

The Windows computer must remain powered on and connected to the internet for local execution and scheduled sends.

5.1 TELEGRAM AUTHENTICATION

The bot must only accept commands and approvals from the authorized Telegram user.

Requirements:

Use an explicit Telegram Chat ID allowlist.
Ignore unauthorized users.
Store the bot token in an environment variable or secure local configuration.
Never hardcode the token.
Never expose credentials in logs.
Validate every callback and approval action locally.
Bind approvals to a specific institute, message, and campaign.
Prevent duplicate approval execution.
Apply approval expiration.
Verify that the approved message has not changed before execution.
5.2 INDIVIDUAL APPROVAL WORKFLOW

Every institute requires an individual explicit approval.

Before sending, Telegram must receive a notification containing:

Institute name.
Phone number.
Personalized message.
Selected WhatsApp account: Profile 40.
Proposed sending time.
Campaign identifier.

Provide these actions:

Approve & Send Now.
Schedule.
Reject / Skip.
Pause Campaign.

Use Telegram inline keyboard buttons.

Every approval must be validated against the local database before execution.

An approval must be bound to:

Contact identifier.
Campaign identifier.
Exact message content or message hash.
Approval record identifier.
Expiration time.

Never execute an approval belonging to another contact or a modified message.

5.3 SCHEDULING THROUGH TELEGRAM

When the user selects Schedule:

Ask for the desired date and time.
Validate the date and time.
Confirm the scheduled operation.
Save the task locally.
Notify the user when execution begins.

All timestamps must use:

Asia/Aden

If the application is closed or Windows is shut down:

Scheduled tasks must remain stored.
No messages should be sent while the application is offline.
Tasks must be re-evaluated safely when the application restarts.
Expired approvals must not execute.
Duplicate executions must be prevented.

Never execute a scheduled message without a valid approval for that exact institute and message.

5.4 TELEGRAM COMMANDS

Implement:

/start — Initialize the bot.
/status — Show campaign and system status.
/pause — Pause campaign execution.
/resume — Resume campaign execution.
/next — Display the next pending institute.
/skip — Skip the current institute.
/help — Display available commands.

Do not overload the bot with unnecessary commands.

5.5 NOTIFICATIONS

Send Telegram notifications for:

New approval requests.
Successful sends.
Failed sends.
Invalid phone numbers.
WhatsApp disconnection.
Scheduled sending events.
Campaign completion.
Application errors requiring attention.
Local application shutdown or startup when useful.
6. CAMPAIGN SCHEDULER

Implement configurable scheduling.

Settings:

Campaign start date.
Campaign start time.
Time interval between messages.
Maximum messages per session.
Allowed sending hours.
Campaign pause/resume.
Manual execution.
Scheduled execution.

All settings must be configurable through the desktop dashboard.

Use safe, configurable intervals.

Do not implement artificial randomization or mechanisms designed to bypass WhatsApp restrictions.

The scheduler must:

Persist its state in SQLite.
Survive application restarts.
Avoid duplicate execution.
Avoid overlapping jobs.
Respect individual approval requirements.
Skip contacts already successfully contacted.
Respect campaign pause state.
Respect approval expiration.
Recover safely from interrupted operations.

If the campaign is paused, no new messages may be sent until explicitly resumed.

If the computer is offline or the application is closed, execution must stop safely.

7. DESKTOP DASHBOARD

Build a clean, professional Windows desktop interface using PySide6.

The interface should prioritize clarity and usability.

MAIN DASHBOARD

Display:

Total institutes.
Pending contacts.
Awaiting approval.
Scheduled messages.
Successfully contacted.
Failed operations.
Uncertain operations.
WhatsApp connection status.
Telegram connection status.
Selected Chrome profile: Profile 40.
Current campaign state.
Last successful synchronization.
Local application status.
MAIN SECTIONS
1. Dashboard

Overview of system activity and campaign progress.

2. Contacts

Display, search, filter, and inspect institutes.

3. Campaigns

Create, start, pause, resume, and review campaigns.

4. Message Template

View TXT template and preview personalized messages.

5. WhatsApp Settings

Display:

Profile Name: Profile 40.
Exact Profile Path.
WhatsApp connection state.
Authentication status.

There must be NO profile-selection dropdown and NO alternative profile options.

6. Telegram Settings

Configure:

Bot credentials.
Authorized Chat ID.
Telegram connection status.
7. Scheduler

Configure dates, times, intervals, and execution limits.

8. Activity Logs

Display sending history, failures, and system events.

9. Build and System Information

Display:

Application version.
Local installation path.
Database status.
Current timezone.
Last startup time.
UI REQUIREMENTS
Professional modern design.
Arabic and English text support.
Proper Arabic right-to-left layout where applicable.
Clear status indicators.
Readable tables.
Confirmation dialogs for critical actions.
No unnecessary animations or decorative complexity.
Clear error messages.
Responsive interface.
Avoid blocking the UI during browser or network operations.
8. DATABASE AND STATE MANAGEMENT

Use SQLite for persistent local state.

Store:

Contact identifiers.
Campaign identifiers.
Approval records.
Scheduling records.
Sending attempts.
Execution results.
Error details.
Fixed Chrome profile path.
Application configuration.
Message hashes.
Approval expiration.
Execution locks.
Audit history.

Use transactions and unique identifiers.

Maintain a reliable relationship between Excel records and internal database records.

Excel is the human-readable contact source.

SQLite maintains execution state and audit history.

The database must not silently overwrite original Excel information.

8.1 LOCAL-FIRST DATA POLICY

The application must be local-first.

Do not introduce cloud databases, permanent backend servers, or unnecessary external infrastructure.

The cloud development environment must only receive files that are intentionally provided for development and testing.

Do not upload the user's contact workbook, private notes, WhatsApp authentication information, or Telegram credentials unnecessarily.

Keep sensitive application data on the user's Windows computer.

9. ERROR HANDLING AND RELIABILITY

Implement robust handling for:

Missing files.
Invalid Excel structure.
Missing message placeholders.
Invalid phone numbers.
Duplicate phone numbers.
Chrome not installed.
Profile 40 not found.
Profile 40 locked.
WhatsApp disconnected.
WhatsApp authentication failure.
Telegram API failures.
Network interruptions.
Browser timeouts.
Unexpected WhatsApp interface changes.
Application restarts during a campaign.
Uncertain sending outcomes.
SQLite database errors.
Corrupted or inaccessible Excel workbooks.
Expired approvals.
Duplicate Telegram callbacks.

Every error must have:

Clear description.
Timestamp.
Associated contact or campaign where applicable.
Recovery action when possible.

Do not mark failed operations as successful.

Do not automatically resend messages when their previous sending outcome is uncertain.

10. PROJECT STRUCTURE

Use a clean and maintainable project structure similar to:

text
IOA/
│
├── main.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── build_windows.bat
├── pyinstaller.spec
│
├── config/
│   └── settings.py
│
├── core/
│   ├── campaign_manager.py
│   ├── contact_manager.py
│   ├── message_engine.py
│   ├── approval_manager.py
│   ├── scheduler.py
│   └── execution_manager.py
│
├── integrations/
│   ├── whatsapp/
│   │   ├── browser_manager.py
│   │   ├── chrome_profile_manager.py
│   │   ├── whatsapp_client.py
│   │   └── message_sender.py
│   │
│   └── telegram/
│       ├── bot.py
│       ├── notifications.py
│       └── approval_handlers.py
│
├── data/
│   ├── database.py
│   ├── excel_manager.py
│   ├── backup_manager.py
│   └── models.py
│
├── ui/
│   ├── main_window.py
│   ├── dashboard.py
│   ├── contacts_view.py
│   ├── campaign_view.py
│   ├── settings_view.py
│   └── logs_view.py
│
├── tests/
│   ├── test_message_engine.py
│   ├── test_excel_manager.py
│   ├── test_database.py
│   ├── test_approval_manager.py
│   ├── test_scheduler.py
│   ├── test_profile_manager.py
│   └── test_execution_manager.py
│
├── logs/
│
├── storage/
│   ├── backups/
│   └── database/
│
└── dist/
    └── IOA.exe


You may adjust the structure when technically justified.

Keep responsibilities separated and avoid unnecessary modules.

11. IMPLEMENTATION PHASES

Work incrementally.

Do not attempt to implement all modules in one massive operation.

Complete each phase, validate it, and then proceed.

PHASE 1 — PROJECT FOUNDATION
Initialize the Python project.
Set up dependencies.
Build the desktop application shell.
Implement configuration management.
Implement logging.
Establish the local-first architecture.
Establish the testing framework.

Deliverable:

A working desktop application shell.

PHASE 2 — EXCEL AND MESSAGE ENGINE
Implement input-directory discovery.
Read Excel data.
Implement flexible column mapping.
Read TXT templates.
Generate personalized messages.
Implement backup and safe Excel updates.
Implement Arabic text handling.

Deliverable:

A working local contact and message management module.

PHASE 3 — FIXED CHROME PROFILE MANAGEMENT
Configure the exact Profile 40 path.
Verify that the profile directory exists.
Implement safe browser lifecycle management.
Handle profile-lock conflicts.
Persist the fixed profile configuration.
Display Profile 40 in the dashboard.
Implement isolated automated tests.

Deliverable:

A validated Chrome profile management module.

Actual Profile 40 verification must take place later on the user's Windows computer.

PHASE 4 — WHATSAPP INTEGRATION
Implement WhatsApp Web integration.
Connect using Profile 40.
Verify authentication.
Open individual conversations.
Prepare and send messages.
Verify sending outcomes.
Handle errors and uncertain states.

Cloud testing must use mocks and simulated browser interactions.

Do not claim actual WhatsApp integration has been verified until it is tested on the user's Windows computer.

Deliverable:

A WhatsApp integration ready for local acceptance testing.

PHASE 5 — TELEGRAM INTEGRATION
Implement the bot.
Implement authorized-user access.
Implement individual approval.
Implement send-now actions.
Implement scheduling actions.
Implement pause/resume.
Implement notifications.
Validate callback security.

Deliverable:

A functioning Telegram integration connected to the local application.

PHASE 6 — CAMPAIGN MANAGEMENT
Implement campaign queue.
Integrate scheduler.
Integrate Excel and SQLite state.
Implement restart recovery.
Prevent duplicate sending.
Handle expired approvals.
Handle uncertain operations.

Deliverable:

A complete campaign management engine.

PHASE 7 — DASHBOARD AND FINALIZATION
Complete the interface.
Add monitoring and activity logs.
Improve error reporting.
Write setup and usage documentation.
Prepare Windows startup and installation procedures.
Build the final executable.
Validate the application package.

Deliverable:

A complete Windows application ready for user installation and testing.

12. CLOUD DEVELOPMENT REQUIREMENTS

This section is mandatory.

The AI development agent must perform the entire development process in its available cloud environment.

12.1 Cloud Development Responsibilities

The agent must:

Initialize the project.
Create the source code.
Install required dependencies.
Implement all modules.
Run automated tests.
Fix discovered errors.
Maintain a clean project structure.
Document implementation decisions.
Prepare a Windows-compatible release.
Provide the final deliverables for download.

Do not ask the user to manually implement modules.

Do not require the user to run individual Python scripts during ordinary development.

12.2 Cloud Environment Limitations

The agent must understand that:

The user's Windows filesystem is not directly accessible.
The user's Chrome Profile 40 is not available in the cloud.
The authenticated WhatsApp account is not available in the cloud.
The local Telegram credentials must be configured by the user.
Actual WhatsApp sending cannot be verified through cloud-only tests.

The agent must not invent test results or claim local integration tests passed when they were not performed.

12.3 Windows Build Requirements

The final application must be built for Windows.

Use PyInstaller or another suitable packaging technology.

Important:

If the cloud development environment runs Linux, do not assume it can produce a fully functional native Windows executable simply by running PyInstaller.

Use one of these approaches:

A Windows-based cloud development environment.
A Windows CI build runner.
A suitable Windows virtual build environment.

The final build must be tested on a compatible Windows environment.

Provide:

IOA.exe or an appropriate installation package.
Required runtime resources.
Application configuration template.
Installation instructions.
Version information.

Do not bundle private user credentials into the executable.

Do not bundle the user's Chrome profile or WhatsApp session.

13. LOCAL INSTALLATION AND FIRST-RUN EXPERIENCE

The final application must provide a straightforward installation and setup experience.

On first launch:

Verify Windows compatibility.
Create required application storage directories.
Initialize the SQLite database.
Verify the configured input directory.
Discover Excel and TXT files.
Allow the user to map Excel columns.
Verify the fixed Profile 40 path.
Configure Telegram credentials.
Validate the authorized Telegram Chat ID.
Display system readiness.

The application must never start a campaign automatically after installation.

The user must explicitly configure and authorize campaign execution.

Provide clear instructions for:

Installing the application.
Configuring Telegram.
Preparing the Excel workbook.
Preparing the TXT template.
Connecting WhatsApp.
Resolving profile-lock conflicts.
Starting and pausing campaigns.
Recovering after a restart.
14. ACCEPTANCE CRITERIA

The project is complete only when the following requirements are satisfied.

14.1 Cloud Development Acceptance
Complete source code exists.
All required modules are implemented.
Automated tests run successfully.
No critical known errors remain.
Windows build is generated using a compatible environment.
The final package is downloadable.
Installation documentation is complete.
Test results are documented accurately.
14.2 Local Application Acceptance
Application launches locally on Windows.
It discovers the specified input directory.
It reads Excel correctly.
It identifies the required contact fields.
It reads TXT templates without changing their content.
It generates correct personalized messages.
It uses ONLY Chrome Profile 40.
It does not discover or offer alternative profiles.
It does not interfere with other Chrome profiles.
It verifies WhatsApp authentication.
It requests individual Telegram approval for every institute.
It supports immediate and scheduled sending.
It respects scheduling settings.
It updates Excel only after confirmed successful sending.
It records timestamps and failures.
It prevents duplicate messages.
It survives application restarts without losing campaign state.
It provides a clear activity dashboard.
It protects Telegram credentials and local configuration.
14.3 Mandatory Chrome Acceptance Tests

Verify on the user's Windows computer:

The application launches WhatsApp using the exact Profile 40 configuration.
No alternative Chrome profile is ever used.
A missing Profile 40 directory stops execution.
A locked Profile 40 directory is handled safely.
The application never terminates unrelated Chrome processes.
The application never extracts or copies authentication secrets.
WhatsApp authentication failure prevents campaign execution.
14.4 Mandatory Approval Acceptance Tests

Verify:

No message can be sent without an individual valid approval.
Unauthorized Telegram users cannot approve or control campaigns.
Expired approvals cannot execute.
Duplicate callbacks cannot cause duplicate sends.
Modified messages invalidate the corresponding approval.
Paused campaigns cannot initiate new sends.
Uncertain outcomes cannot trigger automatic retries.
15. IMPORTANT DEVELOPMENT INSTRUCTIONS

The following instructions are mandatory:

Develop the project entirely in the cloud development environment.
Do not require direct access to the user's Windows computer during development.
Do not assume that local Windows paths are accessible in the cloud.
Do not assume Chrome Profile 40 exists in the cloud.
Do not attempt to use the user's WhatsApp session in the cloud.
Deliver a Windows application that can be downloaded and run locally.
Do not modify the original message text.
Do not use a random Chrome profile.
Use only the exact Profile 40 path.
Do not silently select another WhatsApp account.
Do not send messages without individual approval.
Do not treat message preparation as successful sending.
Do not mark failed or uncertain operations as completed.
Do not introduce unnecessary cloud infrastructure.
Keep the architecture local-first.
Use clear interfaces between modules.
Protect credentials and sensitive data.
Test each implementation phase before proceeding.
Do not claim functionality is complete until it has been implemented and verified.
Distinguish cloud-verified functionality from functionality requiring local Windows testing.

Prioritize reliability, data integrity, security, maintainability, and user control over implementation shortcuts.

16. FINAL DELIVERABLE

Deliver a complete, functional Windows desktop application named:

IOA — Institute Outreach Automation

Include:

Complete Python source code.
Professional desktop dashboard.
WhatsApp Web integration.
Fixed Chrome Profile 40 integration.
Telegram approval bot.
Excel integration.
TXT message-template integration.
Scheduling engine.
SQLite persistence.
Error handling and logs.
Automated test suite.
Dependency file.
Environment configuration example.
Windows executable or installer.
Installation instructions.
User manual.
Build and test report.

The user must be able to download the completed application from the cloud development environment and install it on their Windows computer.

The application must operate locally and use the existing authenticated WhatsApp account.

FINAL CHROME CONFIGURATION — MUST NOT CHANGE
python
CHROME_USER_DATA_DIR = (
    r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data"
)

CHROME_PROFILE_DIRECTORY = "Profile 40"

CHROME_PROFILE_PATH = (
    r"C:\Users\USERW\AppData\Local\Google\Chrome\User Data\Profile 40"
)


The application must exclusively use the existing WhatsApp account authenticated in Profile 40.

No profile discovery.

No profile selection.

No automatic switching.

No fallback to other accounts.

17. STARTING INSTRUCTIONS FOR THE AI AGENT

Start by examining the cloud development environment and its capabilities.

Then:

Confirm the available operating system and whether native Windows building is supported.
Design the project architecture.
Create the project foundation.
Establish automated testing.
Implement the phases incrementally.
Validate every phase before proceeding.
Build the Windows release using a compatible Windows environment.
Generate the complete final deliverables.
Provide the user with download links for the generated files.
Clearly document which features have been tested in the cloud and which require final verification on the user's Windows computer.

Do not stop after producing a project plan.

Do not deliver only sample code or a prototype.

The objective is a complete, maintainable, functional Windows desktop application.

The development takes place in the cloud. The actual WhatsApp automation takes place locally on the user's Windows computer using Profile 40.

This separation is the fundamental architectural requirement of IOA.