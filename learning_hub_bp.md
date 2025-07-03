# Learning Hub Blueprint (`learning_hub_bp`)

## File Location
- `learning_hub/__init__.py`
- `learning_hub/routes.py`

## URL Prefix
`/learning`

## Template Folder
`templates/learning`

## Purpose
The `learning_hub_bp` blueprint provides a platform for financial literacy and ICT skills training, targeting diverse Nigerian audiences (e.g., civil servants, NYSC members, undergraduates) to address foundational skill gaps and combat pretense in tech proficiency. It offers courses, quizzes, progress tracking, and community engagement features.

## Key Features & Functionalities

### Routes
- **GET `/`**: Displays a catalog of courses, filtered by `session['role_filter']` (e.g., `civil_servant`, `nysc`, `agent`).
- **GET `/courses/<course_id>`**: Shows specific course details and lessons.
- **GET/POST `/quiz/<quiz_id>`**: Handles interactive quizzes, including the Reality Check Quiz, saving scores to MongoDB and awarding badges/coins.
- **GET/POST `/progress`**: Tracks user progress (completion percentage, certificates, badges) for authenticated (`user_id`) or anonymous (`session_id`) users.
- **POST `/set_role_filter`**: Stores the selected role in `session['role_filter']` to filter courses.
- **GET/POST `/register_webinar`**: Handles webinar signups, storing data in `webinar_registrations` and sending confirmation emails.
- **GET `/forum`**: Placeholder route redirecting to the main page with a “coming soon” message (planned for future expansion).
- **GET/POST `/admin/course_management`**: Allows admins to upload/edit course content with role-specific assignments. Requires `admin` role.
- **GET `/unsubscribe`**: Manages email notification preferences for course updates and webinars.

### Courses
- **Digital Foundations Course** (`course_id="digital_foundations"`):
  - **Modules**:
    - Computer Basics: Hardware vs. software, file management, keyboard shortcuts.
    - Internet Tools: Email setup/usage, browsing, online safety.
    - AI for Beginners: Introduction to AI tools (e.g., AI in budgeting), with quiz `quiz-digital-foundations-3-1`.
  - **Roles**: `["civil_servant", "nysc", "agent"]` for targeted access.
  - **Purpose**: Addresses foundational ICT gaps for civil servants, NYSC members, and others intimidated by tech.
- **Other Courses**: Financial literacy courses (e.g., budgeting, investing) with role-specific filtering.

### Quizzes
- **Reality Check Quiz** (`id="reality_check_quiz"`):
  - Two questions to assess basic ICT skills (e.g., email usage, software concepts).
  - Action `submit_reality_check` stores results in `session` for anonymous users and returns tailored course recommendations.
  - Awards 3 coins and a “Reality Check” badge upon completion.
- **Other Quizzes**: Linked to lessons (e.g., `quiz-digital-foundations-3-1` for AI budgeting).

### Badge System
- **Badges**:
  - **Digital Starter**: Awarded for completing the first Digital Foundations lesson.
  - **Reality Check**: Awarded for completing the Reality Check Quiz.
- **Storage**: Saved in `badges_earned` (MongoDB) as a list of dictionaries with `title_key` and `title_en`.
- **Purpose**: Encourages engagement and reduces stigma around starting from basics.

### Forms
- **CourseProgressForm**: Tracks lesson completion and badge awards.
- **QuizSubmissionForm**: Handles quiz responses, including Reality Check Quiz.
- **UploadForm**: Admin form for uploading course content, with a `roles` field for selecting applicable roles (`civil_servant`, `nysc`, `agent`, `personal`, `admin`).
- **WebinarRegistrationForm**: Captures webinar signup details (e.g., name, email).

### Database Operations
- **Collections**:
  - `learning_materials`: Stores course metadata, content, and `roles` (list of strings).
  - `progress`: Tracks lesson/quiz completion and `badges_earned` (list of dictionaries).
  - `quiz_scores`: Logs quiz results.
  - `webinar_registrations`: Stores webinar signup data (name, email, registration_date).
- **Operations**:
  - Fetch courses with role filtering (`course_lookup` from MongoDB).
  - Update progress and badges (`save_course_progress`, `get_progress`).
  - Store webinar registrations (`register_webinar`).
  - Seed default courses via `init_storage`.

### Role-Based Access
- **Public Routes**: Accessible to all via `custom_login_required` (supports anonymous sessions).
- **Admin Routes**: Restricted to `admin` role via `requires_role(['admin'])`.
- **Role Filtering**: Courses filtered by `session['role_filter']` (set via `/set_role_filter`).

### UI Integration/Navigation
- Passes `PERSONAL_TOOLS` and `PERSONAL_NAV` for user routes, or `ALL_TOOLS` and `ADMIN_NAV` for admin routes, using `get_role_based_nav()` from `settings.py`.
- Templates: `learning/courses.html`, `learning/lesson.html`, `learning/quiz.html`, `learning/webinar.html`, `learning/admin_management.html`.

### Coin System Integration
- Basic courses (e.g., Digital Foundations) are free/low-cost to encourage participation.
- Advanced courses/quizzes consume coins, logged in `coin_transactions`.
- Awards 3 coins for Reality Check Quiz completion, logged in `coin_transactions`.

### Email Notifications
- Sends course completion certificates, quiz results, and webinar confirmations via Mailersend.
- Includes badge and coin information in emails (e.g., “You earned the Digital Starter badge!”).
- Uses `learning_hub_webinar_registration.html` template for webinar emails, with placeholders for `first_name`, `webinar_date`, `cta_url`, and `unsubscribe_url`.

### Cross-Tool Interactions
- Integrates with `personal_bp` for recent activity feed (e.g., “Earned Digital Starter badge”).
- Uses `news_bp` to share ICT success stories and webinar promotions.
- Leverages `settings.py` for notification preferences and `translations.py` for multilingual support.

### Error Handling
- **404**: Custom page for invalid `course_id` or `quiz_id`.
- **CSRF**: Protects POST routes (e.g., quiz submissions, webinar registrations).
- **Logging**: Logs role filter changes, webinar registrations, and user actions using Python’s `logging` module.
- **User Feedback**: Flash messages for errors (e.g., invalid form inputs, insufficient coins).

### Special Notes
- **Breaking Pretense Culture**: Uses encouraging language in course descriptions and quiz feedback to reduce stigma around starting from basics.
- **Community Engagement**: Webinar registrations and placeholder forum route lay the groundwork for a community interface.
- **Future Enhancements**: Planned offline caching (Service Workers, IndexedDB) and voice accessibility (Web Speech API) to reach underserved groups.

## Dependencies
- **MongoDB**: `get_mongo_db` from `utils.py` for database access.
- **Security**: `requires_role`, `custom_login_required` from `utils.py`.
- **Navigation**: `get_role_based_nav` from `settings.py`.
- **Forms**: Flask-WTF for form handling.
- **Email**: Mailersend for notifications.
- **Coin System**: `check_coin_balance`, `deduct_coin` from `utils.py`.
- **Translations**: `trans` function and `translations.py` for multilingual support.
