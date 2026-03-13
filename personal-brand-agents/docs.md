Architectural Choices
This project follows the supervisor pattern for every agent.

We have 2 supervisor agents. Each one is responsible for catering to a different type of user.

We will refer to them as...
**New College Grads (NCG)** - Those who want to deploy their own personal brand. They will interact with the Data Management Agent
**Audience** - Those who want to interact with someone else's personal brand. They will interact with [XXX's] Personal Brand Agent

**Data Management Agent**
Goal: Usable interface for a NCG to manage facts about themselves
Functionalities:

- Gather profile data
- Gather data from a series of behavorial questions
- Parse data from a resume
- Delete data
- Connect LinkedIn
- Link your data to a **Personal Brand Agent**

**Personal Brand Agent**
Goal: Usable interface for an audience member to learn more about a NCG & represent the NCG in a manner catered towards the audience member.
Functionalities:

- Gather information from an audience member
- Store information about an audience member for tailored responses and for the NCG to view
- Answer questions on behalf of the NCG using their data
- Cater responses to the audience member based on their preferences and aforementioned data
