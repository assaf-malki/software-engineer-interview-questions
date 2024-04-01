import json
import sqlite3

import requests

DATABASE_NAME = 'questions.db'


def fetch_and_save_questions():
    url = "https://leetcode.com/graphql/"
    difficulties = ['HARD', 'MEDIUM']
    batch_size = 1000  # Adjust based on API limit

    try:
        conn = sqlite3.connect(DATABASE_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS questions
                     (title TEXT, titleSlug TEXT PRIMARY KEY, difficulty TEXT, topicTags TEXT, solved BOOLEAN DEFAULT FALSE)''')

        total_questions_fetched = {'HARD': 0, 'MEDIUM': 0}

        for difficulty in difficulties:
            has_more = True
            skip = 0
            while has_more:
                payload_query = {
                    'query': '''
                    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
                        problemsetQuestionList: questionList(
                            categorySlug: $categorySlug
                            limit: $limit
                            skip: $skip
                            filters: $filters
                        ) {
                            questions: data {
                                title
                                titleSlug
                                difficulty
                                topicTags {
                                    name
                                }
                            }
                        }
                    }''',
                    'variables': {'categorySlug': '', 'skip': skip, 'limit': batch_size,
                                  'filters': {'difficulty': difficulty}}
                }
                payload = json.dumps(payload_query)
                headers = {'Content-Type': 'application/json'}

                try:
                    response = requests.post(url, headers=headers, data=payload)
                    response.raise_for_status()  # Raises HTTPError for bad responses
                    data = response.json()['data']['problemsetQuestionList']
                except requests.HTTPError as http_err:
                    print(f'HTTP error occurred: {http_err}')
                    break  # or continue based on your error handling policy
                except requests.RequestException as req_err:
                    print(f'Network error occurred: {req_err}')
                    break  # or continue based on your error handling policy
                except KeyError as key_err:
                    print(f'Error parsing response data: {key_err}')
                    break  # or continue based on your error handling policy

                questions = data.get('questions', [])

                if not questions:
                    break  # Stop if no more questions are fetched

                for question in questions:
                    topic_tags = ', '.join(tag['name'] for tag in question['topicTags'])
                    try:
                        c.execute(
                            "INSERT OR IGNORE INTO questions (title, titleSlug, difficulty, topicTags) VALUES (?, ?, ?, ?)",
                            (question['title'], question['titleSlug'], question['difficulty'], topic_tags))
                        if c.rowcount > 0:
                            total_questions_fetched[difficulty] += 1
                    except sqlite3.DatabaseError as db_err:
                        print(f'Database error occurred: {db_err}')
                        continue  # or break based on your error handling policy

                skip += len(questions)
                has_more = len(questions) == batch_size

        conn.commit()
    except sqlite3.Error as e:
        print(f'An error occurred while connecting to the database: {e}')
    finally:
        conn.close()
