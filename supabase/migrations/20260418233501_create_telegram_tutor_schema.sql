/*
  # Telegram AI Tutor Bot - Complete Database Schema

  ## Overview
  Full schema for a Telegram-based AI personal tutor bot with:
  - Multi-course support with per-course vector stores
  - Adaptive quiz system with spaced repetition (SM-2 algorithm)
  - Flashcard system with spaced repetition
  - Long-term and short-term memory per user per course
  - User preferences and personalization
  - File/document tracking per course
  - Weak topic tracking and mastery scores

  ## Tables
  1. `bot_users` - Telegram users
  2. `courses` - User courses
  3. `course_files` - Uploaded documents per course
  4. `quiz_questions` - Quiz question bank
  5. `quiz_performance` - Per-user quiz answer history with SM-2 data
  6. `flashcards` - Flashcard bank per user per course
  7. `user_preferences` - User settings and preferences
  8. `conversations` - Short-term conversation history
  9. `user_memory` - Long-term educational memory
  10. `topics` - Topic/concept tracking for mastery

  ## Security
  All tables have RLS enabled with policies for authenticated service role access.
  Bot uses service role key, so policies allow service role full access.
*/

-- Users table (Telegram user IDs as primary key)
CREATE TABLE IF NOT EXISTS bot_users (
  id bigint PRIMARY KEY,
  username text,
  first_name text,
  last_name text,
  language_code text DEFAULT 'fa',
  active_course_id uuid,
  onboarded boolean DEFAULT false,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE bot_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to bot_users"
  ON bot_users FOR SELECT
  TO service_role
  USING (true);

CREATE POLICY "Service role insert bot_users"
  ON bot_users FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY "Service role update bot_users"
  ON bot_users FOR UPDATE
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Service role delete bot_users"
  ON bot_users FOR DELETE
  TO service_role
  USING (true);

-- Courses table
CREATE TABLE IF NOT EXISTS courses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text DEFAULT '',
  emoji text DEFAULT '📚',
  file_count int DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE courses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to courses"
  ON courses FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert courses"
  ON courses FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update courses"
  ON courses FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete courses"
  ON courses FOR DELETE TO service_role USING (true);

-- Add foreign key from bot_users.active_course_id to courses.id
ALTER TABLE bot_users ADD CONSTRAINT fk_active_course
  FOREIGN KEY (active_course_id) REFERENCES courses(id) ON DELETE SET NULL;

-- Course files table
CREATE TABLE IF NOT EXISTS course_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  filename text NOT NULL,
  original_filename text NOT NULL,
  file_type text NOT NULL,
  file_size_bytes bigint DEFAULT 0,
  chunk_count int DEFAULT 0,
  indexed boolean DEFAULT false,
  summary text DEFAULT '',
  uploaded_at timestamptz DEFAULT now()
);

ALTER TABLE course_files ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to course_files"
  ON course_files FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert course_files"
  ON course_files FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update course_files"
  ON course_files FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete course_files"
  ON course_files FOR DELETE TO service_role USING (true);

-- Quiz questions table
CREATE TABLE IF NOT EXISTS quiz_questions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  question text NOT NULL,
  answer text NOT NULL,
  options jsonb DEFAULT '[]',
  question_type text DEFAULT 'mcq',
  topic text DEFAULT '',
  difficulty int DEFAULT 3,
  source_file_id uuid REFERENCES course_files(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE quiz_questions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to quiz_questions"
  ON quiz_questions FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert quiz_questions"
  ON quiz_questions FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update quiz_questions"
  ON quiz_questions FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete quiz_questions"
  ON quiz_questions FOR DELETE TO service_role USING (true);

-- Quiz performance (SM-2 spaced repetition data per user per question)
CREATE TABLE IF NOT EXISTS quiz_performance (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  question_id uuid NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  correct boolean NOT NULL,
  user_answer text DEFAULT '',
  answered_at timestamptz DEFAULT now(),
  next_review_at timestamptz DEFAULT now(),
  ease_factor float DEFAULT 2.5,
  interval_days int DEFAULT 1,
  repetitions int DEFAULT 0,
  UNIQUE(user_id, question_id)
);

ALTER TABLE quiz_performance ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to quiz_performance"
  ON quiz_performance FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert quiz_performance"
  ON quiz_performance FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update quiz_performance"
  ON quiz_performance FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete quiz_performance"
  ON quiz_performance FOR DELETE TO service_role USING (true);

-- Flashcards table
CREATE TABLE IF NOT EXISTS flashcards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  front text NOT NULL,
  back text NOT NULL,
  topic text DEFAULT '',
  source text DEFAULT 'manual',
  ease_factor float DEFAULT 2.5,
  interval_days int DEFAULT 1,
  repetitions int DEFAULT 0,
  next_review_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

ALTER TABLE flashcards ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to flashcards"
  ON flashcards FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert flashcards"
  ON flashcards FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update flashcards"
  ON flashcards FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete flashcards"
  ON flashcards FOR DELETE TO service_role USING (true);

-- User preferences
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id bigint PRIMARY KEY REFERENCES bot_users(id) ON DELETE CASCADE,
  answer_mode text DEFAULT 'auto',
  explanation_depth text DEFAULT 'normal',
  output_language text DEFAULT 'fa',
  voice_enabled boolean DEFAULT false,
  socratic_mode boolean DEFAULT false,
  hint_mode boolean DEFAULT false,
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to user_preferences"
  ON user_preferences FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert user_preferences"
  ON user_preferences FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update user_preferences"
  ON user_preferences FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete user_preferences"
  ON user_preferences FOR DELETE TO service_role USING (true);

-- Conversations (short-term memory, last N messages)
CREATE TABLE IF NOT EXISTS conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  course_id uuid REFERENCES courses(id) ON DELETE SET NULL,
  role text NOT NULL,
  content text NOT NULL,
  message_type text DEFAULT 'text',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_course ON conversations(user_id, course_id, created_at DESC);

ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to conversations"
  ON conversations FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert conversations"
  ON conversations FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update conversations"
  ON conversations FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete conversations"
  ON conversations FOR DELETE TO service_role USING (true);

-- Long-term user memory (educational insights)
CREATE TABLE IF NOT EXISTS user_memory (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  course_id uuid REFERENCES courses(id) ON DELETE SET NULL,
  memory_type text NOT NULL,
  topic text DEFAULT '',
  content text NOT NULL,
  importance int DEFAULT 3,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

ALTER TABLE user_memory ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to user_memory"
  ON user_memory FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert user_memory"
  ON user_memory FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update user_memory"
  ON user_memory FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete user_memory"
  ON user_memory FOR DELETE TO service_role USING (true);

-- Topic mastery tracking
CREATE TABLE IF NOT EXISTS topic_mastery (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES bot_users(id) ON DELETE CASCADE,
  course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  topic text NOT NULL,
  mastery_score float DEFAULT 0.0,
  total_attempts int DEFAULT 0,
  correct_attempts int DEFAULT 0,
  last_activity_at timestamptz DEFAULT now(),
  UNIQUE(user_id, course_id, topic)
);

ALTER TABLE topic_mastery ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to topic_mastery"
  ON topic_mastery FOR SELECT TO service_role USING (true);

CREATE POLICY "Service role insert topic_mastery"
  ON topic_mastery FOR INSERT TO service_role WITH CHECK (true);

CREATE POLICY "Service role update topic_mastery"
  ON topic_mastery FOR UPDATE TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "Service role delete topic_mastery"
  ON topic_mastery FOR DELETE TO service_role USING (true);
