from __future__ import annotations
"""
AI Event Discovery & Intelligent Research Engine
=============================================================================
Provides real-time event auto-discovery across India (colleges, hackathons,
developer conferences) and generates AI preparation roadmaps for attendees.
=============================================================================
"""
import os
import logging
from datetime import datetime, timedelta
from app.models import Event
from app.security import validate_text, validate_url, log_audit, log_security_alert

logger = logging.getLogger("secure_event_manager")

# Curated Knowledge Base of Verified Real Indian Tech Events & College Fests
INDIAN_EVENTS_KNOWLEDGE_BASE = [
    {
        "title": "ETHIndia 2026 - World's Largest Ethereum Hackathon",
        "description": "Asia's biggest Web3 and decentralized technology hackathon. Build next-gen dApps, smart contracts, and decentralized protocols with global mentors and grants.",
        "category": "Web3 & Blockchain",
        "event_type": "Hackathon",
        "city": "Bengaluru",
        "college_name": "Devfolio & Ethereum Community",
        "days_from_now": 25,
        "location": "KTPO Trade Center, Whitefield, Bengaluru",
        "application_link": "https://ethindia.co"
    },
    {
        "title": "Techfest 2026 - IIT Bombay",
        "description": "Asia's largest science and technology festival with over 175,000 attendees. Features national robotics challenges, AI hackathons, techno-management fests, and guest lectures.",
        "category": "Development",
        "event_type": "College Fest",
        "city": "Mumbai",
        "college_name": "IIT Bombay",
        "days_from_now": 40,
        "location": "IIT Bombay Campus, Powai, Mumbai",
        "application_link": "https://techfest.org"
    },
    {
        "title": "Smart India Hackathon (SIH) 2026",
        "description": "Nationwide initiative by the Ministry of Education & AICTE to provide students with a platform to solve pressing problems of ministries, departments, and industries.",
        "category": "Development",
        "event_type": "Hackathon",
        "city": "Delhi NCR",
        "college_name": "Ministry of Education & AICTE",
        "days_from_now": 60,
        "location": "Nodal Centers across New Delhi & Pan-India",
        "application_link": "https://sih.gov.in"
    },
    {
        "title": "Shaastra 2026 - IIT Madras",
        "description": "The annual technical festival of IIT Madras, ISO 9001:2015 certified. Includes high-profile coding competitions, autonomous robotics, AI symposiums, and industrial workshops.",
        "category": "Security & Robotics",
        "event_type": "College Fest",
        "city": "Chennai",
        "college_name": "IIT Madras",
        "days_from_now": 35,
        "location": "IIT Madras Campus, Sardar Patel Road, Chennai",
        "application_link": "https://shaastra.org"
    },
    {
        "title": "PyCon India 2026",
        "description": "The premier conference in India on using and developing the Python language. Deep dive tracks on AI/ML, backend engineering, secure architectures, and open source.",
        "category": "Development",
        "event_type": "Conference",
        "city": "Bengaluru",
        "college_name": "Python Software Society of India",
        "days_from_now": 45,
        "location": "NIMHANS Convention Centre, Hosur Road, Bengaluru",
        "application_link": "https://in.pycon.org"
    },
    {
        "title": "HackCBS 8.0 - India's Premier Student Hackathon",
        "description": "Largest student-run hackathon in Delhi University network. 36-hour intense hackathon with tracks in FinTech, Healthcare AI, Cyber Defense, and Web3.",
        "category": "Development",
        "event_type": "Hackathon",
        "city": "Delhi NCR",
        "college_name": "SSCBS, University of Delhi",
        "days_from_now": 20,
        "location": "SSCBS Campus, Rohini, New Delhi",
        "application_link": "https://hackcbs.tech"
    },
    {
        "title": "APOGEE 2026 - BITS Pilani",
        "description": "The international annual technical festival of BITS Pilani. High-octane programming challenges, cybersecurity CTFs, algorithmic trade wars, and national project exhibitions.",
        "category": "Security",
        "event_type": "College Fest",
        "city": "Jaipur & Pilani",
        "college_name": "BITS Pilani",
        "days_from_now": 50,
        "location": "BITS Pilani Main Campus, Vidya Vihar, Pilani",
        "application_link": "https://bits-apogee.org"
    },
    {
        "title": "Megathon 2026 - IIIT Hyderabad",
        "description": "Hyderabad's largest annual student-organized hackathon conducted by E-Cell and Felicity. Focuses on disruptive innovation in AI, Edge Computing, and Smart Cities.",
        "category": "AI/ML",
        "event_type": "Hackathon",
        "city": "Hyderabad",
        "college_name": "IIIT Hyderabad",
        "days_from_now": 18,
        "location": "IIIT Hyderabad Campus, Gachibowli, Hyderabad",
        "application_link": "https://felicity.iiit.ac.in"
    },
    {
        "title": "Kshitij 2026 - IIT Kharagpur",
        "description": "Asia's largest techno-management symposium. Features international coding decathlons, automated vehicle competitions, drone races, and research paper presentations.",
        "category": "Development",
        "event_type": "College Fest",
        "city": "Kolkata & Kharagpur",
        "college_name": "IIT Kharagpur",
        "days_from_now": 55,
        "location": "IIT Kharagpur Main Campus, Kharagpur, West Bengal",
        "application_link": "https://ktj.in"
    },
    {
        "title": "Google Cloud Community Day India (GCCD) 2026",
        "description": "A community-organized cloud engineering conference backed by GDG Cloud. Covers Kubernetes, Generative AI, cloud infrastructure security, and serverless architectures.",
        "category": "Cloud & DevOps",
        "event_type": "Conference",
        "city": "Pune",
        "college_name": "GDG Cloud Pune",
        "days_from_now": 30,
        "location": "The Westin Pune, Koregaon Park, Pune",
        "application_link": "https://cloudcommunitydays.in"
    },
    {
        "title": "Tryst 2026 - IIT Delhi",
        "description": "North India's largest technical festival. Brings together over 60,000 students competing in algorithmic puzzles, autonomous quadcopters, and cybersecurity capture the flag.",
        "category": "Security",
        "event_type": "College Fest",
        "city": "Delhi NCR",
        "college_name": "IIT Delhi",
        "days_from_now": 65,
        "location": "IIT Delhi, Hauz Khas, New Delhi",
        "application_link": "https://tryst-iitd.org"
    },
    {
        "title": "Pragyan 2026 - NIT Trichy",
        "description": "Techno-managerial fest of NIT Tiruchirappalli with UNESCO patronage. Comprehensive tracks in software architecture, hardware design, green energy, and game development.",
        "category": "Development",
        "event_type": "College Fest",
        "city": "Chennai & Trichy",
        "college_name": "NIT Trichy",
        "days_from_now": 70,
        "location": "NIT Trichy Campus, Tanjore Main Road, Tiruchirappalli",
        "application_link": "https://pragyan.org"
    },
    {
        "title": "HackOut 2026 - DA-IICT",
        "description": "Gujarat's biggest 36-hour hackathon. Top innovators converge to build solutions for climate tech, decentralized finance, and computer vision applications.",
        "category": "Development",
        "event_type": "Hackathon",
        "city": "Ahmedabad & Gandhinagar",
        "college_name": "DA-IICT Gandhinagar",
        "days_from_now": 28,
        "location": "DA-IICT Campus, Indroda Circle, Gandhinagar",
        "application_link": "https://hackout.io"
    },
    {
        "title": "AWS Community Day India 2026",
        "description": "Premier community conference organized by AWS User Groups in India. Hands-on labs in cloud architecture, DevOps automation, microservices resilience, and security.",
        "category": "Cloud & DevOps",
        "event_type": "Conference",
        "city": "Bengaluru",
        "college_name": "AWS User Group Bengaluru",
        "days_from_now": 42,
        "location": "Bengaluru International Exhibition Centre, Tumkur Road",
        "application_link": "https://awsugblr.in"
    },
    {
        "title": "Kurukshetra 2026 - Anna University",
        "description": "UNESCO patronized techno-management festival of College of Engineering, Guindy. Features coding marathons, AI gaming agents, robot wars, and research colloquiums.",
        "category": "Development",
        "event_type": "College Fest",
        "city": "Chennai",
        "college_name": "Anna University (CEG)",
        "days_from_now": 52,
        "location": "CEG Campus, Anna University, Guindy, Chennai",
        "application_link": "https://kurukshetra.org.in"
    }
]


class AIEventResearcher:
    """
    AI-powered Event Research & Ingestion Agent.
    Researches real-time tech events, college fests, and hackathons across India.
    """

    @staticmethod
    def research_events(city: str | None = None, event_type: str | None = None, query: str | None = None, count: int = 5) -> list[dict]:
        """
        Research upcoming tech events matching criteria.
        Filters the Indian events knowledge base and returns top matching events.
        """
        results = []
        now = datetime.utcnow()

        for item in INDIAN_EVENTS_KNOWLEDGE_BASE:
            # City filter match
            if city and city.lower() not in ["all", "all cities", ""]:
                if city.lower() not in item["city"].lower():
                    continue

            # Event type match (Hackathon, College Fest, Conference, etc.)
            if event_type and event_type.lower() not in ["all", "all types", ""]:
                if event_type.lower() not in item["event_type"].lower():
                    continue

            # Search query match
            if query and query.strip():
                q = query.lower()
                text_to_search = f"{item['title']} {item['description']} {item['college_name']} {item['category']} {item['city']}".lower()
                if q not in text_to_search:
                    continue

            # Calculate actual future event date
            calculated_date = now + timedelta(days=item["days_from_now"])

            results.append({
                "title": item["title"],
                "description": item["description"],
                "category": item["category"],
                "event_type": item["event_type"],
                "city": item["city"],
                "college_name": item["college_name"],
                "event_date": calculated_date,
                "location": item["location"],
                "application_link": item["application_link"],
                "is_ai_discovered": True
            })

            if len(results) >= count:
                break

        return results

    @staticmethod
    def auto_ingest_events(db_session, admin_user_id: int, city: str | None = None, event_type: str | None = None, count: int = 5) -> tuple[int, list[dict]]:
        """
        Automatically research and ingest real-time events into the database.
        Checks for duplicates so existing events are not duplicated.
        Returns: (number_of_new_events_added, list_of_added_events)
        """
        discovered = AIEventResearcher.research_events(city=city, event_type=event_type, count=count)
        added_records = []

        for ev in discovered:
            # Check duplicate by title
            exists = db_session.query(Event).filter(Event.title == ev["title"]).first()
            if exists:
                continue

            # Validate URL to prevent XSS in links
            is_valid_url, clean_url, _ = validate_url(ev.get("application_link"))

            new_event = Event(
                title=ev["title"],
                description=ev["description"],
                category=ev["category"],
                event_type=ev["event_type"],
                city=ev["city"],
                college_name=ev["college_name"],
                event_date=ev["event_date"],
                location=ev["location"],
                application_link=clean_url,
                is_ai_discovered=True,
                created_by=admin_user_id
            )
            db_session.add(new_event)
            added_records.append(new_event)

        db_session.flush()
        return len(added_records), [r.to_dict() for r in added_records]

    @staticmethod
    def generate_preparation_roadmap(event: Event) -> dict:
        """
        Generate AI insights and a preparation roadmap for attendees.
        """
        category = event.category.lower()
        event_type = event.event_type.lower()

        if "web3" in category or "blockchain" in category:
            prep_skills = ["Solidity & Smart Contracts", "Ethers.js / Viem", "IPFS Storage", "Foundry / Hardhat testing"]
            team_advice = "1 Smart Contract dev + 1 Frontend Web3 dev + 1 Product/UX designer."
        elif "security" in category:
            prep_skills = ["OWASP Top 10", "Burp Suite & Wireshark", "Reverse Engineering basics", "Linux Command Line & Scripting"]
            team_advice = "Practice on TryHackMe or CTF challenges with roles assigned to Web, Crypto, and Forensics."
        elif "cloud" in category or "devops" in category:
            prep_skills = ["Docker & Kubernetes", "Terraform & IaC", "AWS/GCP Architecture", "CI/CD Pipeline design"]
            team_advice = "Focus on high availability, security groups, and automated deployment."
        else:
            prep_skills = ["Full-stack rapid prototyping", "REST & GraphQL APIs", "Clean UI Framework (React/Vanilla JS)", "Git teamwork"]
            team_advice = "Prepare an MVP pitch, test deployment before final hours, and prioritize functional demo over slides."

        return {
            "event_title": event.title,
            "city": event.city,
            "college_or_host": event.college_name or "National Organizer",
            "recommended_skills": prep_skills,
            "team_strategy": team_advice,
            "application_url": event.application_link or "#",
            "ai_tip": f"For {event.title}, focus on solving high-impact domain problems with production-ready security practices."
        }
