# Questions That Need AI vs Questions That Do Not

The assistant should use AI when a question requires understanding, explanation, synthesis, or personalization. Deterministic questions that can be answered with rules or stored data do not need AI.

| # | Question | Needs AI? | Reason |
|---:|---|:---:|---|
| 1 | I am a first-year student. How should I plan my first week at university? | Yes | It requires a personalized plan based on the student's situation and goals. |
| 2 | Can you explain recursion in simple terms with an example? | Yes | It requires generating an explanation suited to the student's level. |
| 3 | I do not understand my lecturer's feedback. What should I improve first? | Yes | It requires interpreting feedback and prioritizing possible improvements. |
| 4 | Help me create a three-day study plan for my programming exam. | Yes | It requires combining the subject, available time, and study goals into a plan. |
| 5 | Which study method would suit me if I easily lose concentration? | Yes | It requires reasoning about the student's needs and providing a suitable recommendation. |
| 6 | Summarize these lecture notes into five key points. | Yes | It requires understanding and condensing unstructured text. |
| 7 | Compare studying alone with studying in a group for this assignment. | Yes | It requires a contextual comparison of advantages and disadvantages. |
| 8 | I have two deadlines tomorrow. How should I prioritize my work? | Yes | It requires weighing factors such as difficulty, time, and importance. |
| 9 | Can you suggest a polite email asking my lecturer for an extension? | Yes | It requires generating natural language with an appropriate tone. |
| 10 | I feel overwhelmed by my coursework. What manageable steps can I take? | Yes | It requires a context-aware response with practical suggestions. |
| 11 | Where is the Training Office? | No | The room can be retrieved directly from `data/offices.csv`. |
| 12 | When does the Library open? | No | The opening hours can be retrieved directly from stored data. |
| 13 | Where is the IT Helpdesk? | No | It is a simple office lookup. |
| 14 | What are the opening hours of Student Affairs? | No | The answer is already stored in the office directory. |
| 15 | Is the Library open on Saturday? | No | A rule can determine the answer from the stored `Mon-Sat` schedule. |
| 16 | List all campus offices. | No | The assistant only needs to list the rows in the office directory. |
| 17 | Which offices are open after 4:30 PM? | No | The result can be found by filtering the stored closing times. |
| 18 | How many offices are in the directory? | No | The assistant only needs to count the stored records. |
| 19 | What commands can this assistant handle? | No | The assistant can return a fixed list of supported commands. |
| 20 | Who owns the office dataset? | No | The answer can be read directly from `data/README.md`. |
