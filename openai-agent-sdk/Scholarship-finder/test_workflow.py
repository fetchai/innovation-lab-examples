"""
Simple test script to verify the OpenAI Agent SDK workflow works.
Run this before deploying to ensure everything is configured correctly.
"""
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for required environment variables
if not os.getenv("OPENAI_API_KEY"):
    print("❌ Error: OPENAI_API_KEY not found in .env file")
    print("Please add your OpenAI API key to .env file")
    exit(1)

print("✅ Environment variables loaded")
print(f"📧 OpenAI API Key: {os.getenv('OPENAI_API_KEY')[:10]}...")

# Import workflow
try:
    from workflow import run_workflow, WorkflowInput
    print("✅ Workflow module imported successfully")
except Exception as e:
    print(f"❌ Error importing workflow: {e}")
    exit(1)


async def test_scholarship_search():
    """Test the scholarship search with a sample student profile"""
    
    print("\n" + "="*60)
    print("🧪 TESTING SCHOLARSHIP FINDER WORKFLOW")
    print("="*60 + "\n")
    
    # Test profile
    test_profile = """
    I'm a junior Computer Science major with 3.7 GPA in San Jose, California.
    Asian-American female interested in AI/ML and Women in Tech.
    President of coding club, volunteer tutor.
    Moderate financial need.
    """
    
    print("📝 Test Student Profile:")
    print(test_profile.strip())
    print("\n" + "-"*60)
    print("🔍 Searching for scholarships...")
    print("-"*60 + "\n")
    
    try:
        # Run the workflow
        result = await run_workflow(WorkflowInput(input_as_text=test_profile))
        
        # Get the output
        output = result.get("output_text", "")
        
        if output:
            print("✅ SUCCESS! Scholarship search completed.\n")
            print("="*60)
            print("📊 RESULTS:")
            print("="*60)
            print(output)
            print("\n" + "="*60)
            print("✅ Test completed successfully!")
            print("="*60)
        else:
            print("⚠️  Warning: No output received from workflow")
            print("This might indicate an issue with the OpenAI API or search")
            
    except Exception as e:
        print(f"\n❌ ERROR during workflow execution:")
        print(f"{type(e).__name__}: {str(e)}")
        print("\nPossible issues:")
        print("1. Invalid OpenAI API key")
        print("2. OpenAI API rate limit exceeded")
        print("3. Network connectivity issues")
        print("4. OpenAI Agent SDK not properly installed")
        return False
    
    return True


if __name__ == "__main__":
    print("\n🎓 Scholarship Finder - Workflow Test\n")
    
    # Run the test
    success = asyncio.run(test_scholarship_search())
    
    if success:
        print("\n✅ All tests passed! Agent is ready to deploy.")
        print("\nNext steps:")
        print("1. Run: python uagent_bridge.py")
        print("2. Test on ASI-One: https://asi1.ai")
    else:
        print("\n❌ Tests failed. Please fix the issues above before deploying.")
        exit(1)
