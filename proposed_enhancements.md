# Proposed Enhancements

This document outlines planned and implemented enhancements to FiCore Africa, focusing on addressing ICT skill gaps among civil servants, undergraduates, NYSC members, and other groups in Nigeria.

## Implemented Enhancements
- **Digital Foundations Course**:
  - Added to `learning_hub_bp` with modules for computer basics, internet tools, and AI for beginners.
  - Supports role-specific filtering (`civil_servant`, `nysc`, `agent`).
  - Includes quiz `quiz-digital-foundations-3-1` for AI budgeting.
- **Reality Check Quiz**:
  - Assesses basic ICT skills and provides tailored course recommendations.
  - Awards 3 coins and “Reality Check” badge upon completion.
- **Role-Specific Tracks**:
  - Added `roles` field to courses and `UploadForm`.
  - Implemented `/set_role_filter` route for dynamic course filtering.
- **Badge System**:
  - Introduced “Digital Starter” and “Reality Check” badges to encourage learning and reduce pretense.
  - Stored in `badges_earned` in MongoDB.
- **Community Engagement**:
  - Added `/register_webinar` route for webinar signups, with MongoDB storage and email confirmations.
  - Placeholder `/forum` route for future community interface.

## Planned Enhancements
- **Offline Usage**:
  - **Purpose**: Enable access to `learning_hub_bp` courses, `news_bp` articles, and `taxation_bp` guides in low-connectivity areas.
  - **Implementation**:
    - Use Service Workers to cache course materials (videos, PDFs) and news articles.
    - Store user progress in IndexedDB, syncing with MongoDB when online.
  - **Impact**: Increases accessibility for civil servants and NYSC members in rural regions.
- **Voice Accessibility**:
  - **Purpose**: Make courses accessible to low-literacy or tech-averse users.
  - **Implementation**:
    - Integrate Web Speech API to read course content and quiz questions in English/Hausa.
    - Allow voice input for quiz answers.
    - Add ARIA attributes to templates.
  - **Impact**: Enhances inclusivity for older civil servants and lecturers.
- **AI Suggestions**:
  - **Purpose**: Provide personalized ICT and financial advice.
  - **Implementation**:
    - Integrate xAI’s Grok API for tailored course recommendations in `learning_hub_bp`.
    - Offer AI-driven tax tips in `taxation_bp` and news summaries in `news_bp`.
    - Gate premium features with coins.
  - **Impact**: Aligns with Nigeria’s 3 Million Technical Talent Programme.
- **Full Community Forum**:
  - **Purpose**: Foster peer support and reduce stigma around starting from basics.
  - **Implementation**: Expand `/forum` route with a discussion interface, storing posts in a `forum_posts` MongoDB collection.
  - **Impact**: Builds a supportive learning community.
- **Additional Badges**:
  - Introduce badges for other courses (e.g., “Email Master” for internet tools module).
  - Tie badges to milestones (e.g., completing 5 lessons).

## Recommended Implementation Order
1. **Offline Usage**: Prioritize to reach underserved groups.
2. **Voice Accessibility**: Enhance inclusivity for tech-averse users.
3. **Full Community Forum**: Build on webinar feature for community engagement.
4. **AI Suggestions**: Implement last, requiring foundational ICT skills.
5. **Additional Badges**: Add incrementally to maintain engagement.

## Integration with ICT Training Goals
- **Target Audiences**: Civil servants, undergraduates, NYSC members, NGO staff, lecturers, company staff.
- **Goal**: Address ICT gaps (e.g., email, Microsoft Office) before introducing AI.
- **Strategy**:
  - Use `learning_hub_bp` for beginner-friendly courses with role-specific tracks.
  - Promote success stories via `news_bp` to normalize starting from basics.
  - Leverage webinars and future forum for community engagement.
