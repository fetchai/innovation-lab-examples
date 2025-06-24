
from crewai import Task

class BloodReportTasks:
    def analyze_blood_report(self, agent, pdf_path):
        return Task(
            description=f'Analyze the blood test report provided in the PDF file at {pdf_path}. Summarize key health indicators, including their significance, normal ranges, and potential health implications for abnormal results. Ensure the analysis is detailed and medically accurate, suitable, provied medicine and medicine link medications for a senior blood report analyst .',
            expected_output='A Markdown file containing a detailed summary of key health indicators, including their values, reference ranges, and explanations of their significance.',
            agent=agent,
            output_file='output/blood_report_summary.md'
        )

    def generate_recommendations(self, agent, context):
        return Task(
            description='Provide detailed health recommendations for each blood test indicator in the summary, including what the indicator means, how to control abnormal results, additional context, dietary advice, exercise routines, provoed medicine and medicine link medications (with a disclaimer to consult a healthcare provider), and lifestyle changes. Include information from related articles and their URLs. Citing source URLs is mandatory And also provied the hospital, clinic and lab map link accordind to lab location area city.',
            expected_output='A Markdown file containing detailed health recommendations for each indicator, including control measures, explanations, and source URLs.',
            agent=agent,
            context=context,
            output_file='output/health_recommendations.md'
        )
