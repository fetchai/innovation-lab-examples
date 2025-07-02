# Meeting Preparation Agent
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)<br />

**Description**: AI agent that helps you prepare for important meetings by researching participants, analyzing industry trends, and developing strategic talking points. It is a crew of four agents all working on different specialized tasks to give the final result.

**1. Research Specialist**
Conducts thorough research on people and companies
Uncovers detailed participant information

**2. Industry Analyst**
Analyzes current industry trends, challenges, and opportunities
Identifies strategic advantages and market context

**3. Meeting Strategy Advisor**
Develops talking points, questions, and strategic angles
Ensures meeting objectives are achieved

**4. Summary and Briefing Coordinator**
Combined role: Handles both summary AND briefing
Compiles all research, analysis, and strategic insights
Creates the final concise, informative briefing document

**How they work together**
- Research Agent finds info about participants/companies
- Industry Analysis Agent adds business context and trends
- Strategy Agent synthesizes everything into actionable meeting preparation

**Input/Output**

**Input** : Natural language which has the email of the person you are meeting with, the context of the meeting and objective of the meeting.

**Output** : Complete meeting brief with participant research, industry insights, and strategic recommendations



**Input Data Model**
```
class ParameterMessage(Model):
    message: str

```

**Output Data Model**
```
class ResponseMessage(Model):
    response: str
```

**Example Query**
```
I have a meeting with garry@ycombinator.com tomorrow. It's a pitch meeting for YC batch application. My objective is to clearly communicate our problem-solution fit and get valuable feedback on our startup idea.
```