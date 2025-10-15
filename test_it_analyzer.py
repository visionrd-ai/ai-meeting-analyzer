"""
Quick test script to verify IT-focused analysis
Run this to test without recording audio
"""

import os
from dotenv import load_dotenv
from summarizer import MeetingSummarizer
import json

load_dotenv()

# Test scenarios with common IT mistakes
test_scenarios = {
    "Azure AKS Security Issue": [
        "We're setting up an AKS cluster in Azure.",
        "The jump box will be on a different subnet from the cluster.",
        "We'll use VNet peering to connect them for security.",
    ],
    
    "AWS EC2 Security Misconfiguration": [
        "For our EC2 instances, we need SSH access.",
        "Let's open port 22 from any IP address to make testing easier.",
        "We can restrict it later after testing is done.",
    ],
    
    "Database Security Issue": [
        "We'll deploy MongoDB on EC2 instances for our application.",
        "For simplicity, let's hardcode the database credentials in the app config.",
        "The admin password will be 'admin123' for now.",
    ],
    
    "Kubernetes Single Point of Failure": [
        "Our AKS cluster will have 3 nodes initially.",
        "All nodes will be in the same availability zone to reduce networking latency.",
        "We'll add more zones later if we need high availability.",
    ],
    
    "CI/CD Resource Under-provisioning": [
        "We need a Jenkins server for CI/CD.",
        "Let's use a t2.micro instance to save costs.",
        "It should be fine for our current team size.",
    ]
}

def main():
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        print("❌ XAI_API_KEY not found in environment")
        print("Set it: export XAI_API_KEY='your-key'")
        return
    
    print("\n" + "="*80)
    print("🧪 IT MEETING ANALYZER - TEST SUITE")
    print("="*80)
    
    for scenario_name, transcript in test_scenarios.items():
        print(f"\n{'='*80}")
        print(f"📋 SCENARIO: {scenario_name}")
        print(f"{'='*80}\n")
        
        # Create fresh summarizer for each scenario
        summarizer = MeetingSummarizer(api_key)
        
        # Simulate meeting discussion
        print("💬 Meeting Transcript:")
        for i, segment in enumerate(transcript, 1):
            print(f"   [{i}] {segment}")
        
        # Add all segments
        print("\n🔍 Analyzing with Grok...\n")
        analysis = None
        for segment in transcript:
            result = summarizer.add_transcript(segment)
            if result:
                analysis = result
        
        # If not enough words, force analysis
        if not analysis:
            analysis = summarizer._analyze_current_state()
        
        # Display results
        if analysis:
            print("="*80)
            print("💡 GROK AI ANALYSIS")
            print("="*80)
            
            # Technical Overview
            print(f"\n📊 TECHNICAL OVERVIEW:")
            print(f"   {analysis.get('technical_analysis', 'N/A')}\n")
            
            # Issues
            issues = analysis.get('potential_issues', [])
            if issues:
                print(f"⚠️  POTENTIAL ISSUES ({len(issues)}):")
                for i, issue in enumerate(issues, 1):
                    print(f"   {i}. {issue}")
                print()
            else:
                print("✓ No issues detected\n")
            
            # Recommendations
            recs = analysis.get('recommendations', [])
            if recs:
                print(f"✅ RECOMMENDATIONS ({len(recs)}):")
                for i, rec in enumerate(recs, 1):
                    print(f"   {i}. {rec}")
                print()
            
            # Questions
            questions = analysis.get('clarifying_questions', [])
            if questions:
                print(f"❓ CLARIFYING QUESTIONS ({len(questions)}):")
                for i, q in enumerate(questions, 1):
                    print(f"   {i}. {q}")
                print()
            
            # Action Items
            actions = analysis.get('action_items', [])
            if actions:
                print(f"📋 ACTION ITEMS ({len(actions)}):")
                for i, a in enumerate(actions, 1):
                    print(f"   {i}. {a}")
                print()
        else:
            print("❌ No analysis generated")
        
        print("\n" + "-"*80)
        input("Press Enter to continue to next scenario...")
    
    print("\n" + "="*80)
    print("✅ TEST SUITE COMPLETE")
    print("="*80)
    print("\nWhat did you observe?")
    print("- Did Grok identify the security/architectural issues?")
    print("- Were the recommendations specific and actionable?")
    print("- Did it ask relevant clarifying questions?")
    print("\nIf yes, the system is working correctly! 🎉")

if __name__ == "__main__":
    main()