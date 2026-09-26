"""
MediVault Local — Patient Portal Database Migration
Creates patient_users and dietary_guidelines tables, and seeds demo patient accounts.
Safe to run multiple times (uses IF NOT EXISTS and OR IGNORE).
"""

import os
import sys
import sqlite3

# Add project root to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from backend.auth import hash_password

DB_PATH = os.path.join(BASE_DIR, "database", "medivault.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")


def migrate_patient_portal():
    """
    Creates patient portal tables and seeds demo accounts.
    Safe to call from init_db() or standalone.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    cursor = conn.cursor()

    # Create patient_users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patient_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT NOT NULL,
            date_of_birth TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
        )
    """)

    # Create dietary_guidelines table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dietary_guidelines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_keyword TEXT NOT NULL COLLATE NOCASE,
            category TEXT NOT NULL CHECK(category IN ('FOOD_RECOMMENDED', 'FOOD_AVOID', 'WELLNESS_TIP')),
            item TEXT NOT NULL,
            rationale TEXT NOT NULL,
            UNIQUE(condition_keyword, category, item)
        )
    """)

    # Seed demo patient accounts (Password: Patient123!)
    demo_patients = [
        ("PT-101", "john.doe", "Patient123!", "John Doe", "1962-03-15"),
        ("PT-102", "sarah.connor", "Patient123!", "Sarah Connor", "1984-07-22"),
        ("PT-103", "robert.smith", "Patient123!", "Robert Smith", "1955-11-08"),
    ]

    for patient_id, username, password, full_name, dob in demo_patients:
        # Check if already exists
        cursor.execute("SELECT id FROM patient_users WHERE username = ?", (username,))
        if cursor.fetchone():
            continue

        salt_hex, hash_hex = hash_password(password)
        cursor.execute("""
            INSERT OR IGNORE INTO patient_users (patient_id, username, password_hash, salt, full_name, date_of_birth)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (patient_id, username, hash_hex, salt_hex, full_name, dob))

    # Run dietary_guidelines seed data from schema.sql
    # (The schema.sql INSERT OR IGNORE statements handle this when init_db runs the full schema)
    # But in case init_db was already run before the schema update, seed manually here:
    dietary_seeds = [
        # Kidney Disease
        ("kidney disease", "FOOD_RECOMMENDED", "Low-sodium vegetables (cucumbers, bell peppers, cabbage)", "Reduces fluid retention and hypertension burden on damaged nephrons"),
        ("kidney disease", "FOOD_RECOMMENDED", "Egg whites and skinless chicken", "High-quality protein with lower phosphorus than red meat — gentler on kidneys"),
        ("kidney disease", "FOOD_RECOMMENDED", "Blueberries, strawberries, and red grapes", "Rich in antioxidants that reduce oxidative stress on renal tissue"),
        ("kidney disease", "FOOD_AVOID", "Bananas, oranges, and potatoes", "Very high potassium content — risks dangerous heart rhythm problems in kidney disease"),
        ("kidney disease", "FOOD_AVOID", "Processed meats, canned soups, and fast food", "Extremely high sodium accelerates kidney damage and causes swelling"),
        ("kidney disease", "FOOD_AVOID", "Dark colas and dairy in excess", "High phosphorus contributes to bone weakening and calcium deposits"),
        ("kidney disease", "WELLNESS_TIP", "Track your daily fluid intake (ask your doctor for your personal limit)", "Too much fluid can cause dangerous swelling; too little speeds kidney decline"),
        ("kidney disease", "WELLNESS_TIP", "Weigh yourself every morning before eating", "Sudden weight gain (2+ lbs overnight) may signal fluid retention — contact your care team"),
        # Diabetes
        ("diabetes", "FOOD_RECOMMENDED", "Non-starchy vegetables, legumes, and whole grains", "Low glycemic index foods prevent dangerous blood sugar spikes after meals"),
        ("diabetes", "FOOD_RECOMMENDED", "Nuts (almonds, walnuts) and seeds", "Healthy fats and fiber slow glucose absorption and improve insulin response"),
        ("diabetes", "FOOD_RECOMMENDED", "Fatty fish (salmon, sardines) twice per week", "Omega-3 fatty acids reduce cardiovascular risk — the #1 cause of death in diabetes"),
        ("diabetes", "FOOD_AVOID", "White bread, white rice, and sugary drinks", "Rapid glucose absorption causes dangerous blood sugar spikes"),
        ("diabetes", "FOOD_AVOID", "Fruit juices and dried fruits", "Concentrated natural sugars raise blood sugar almost as fast as candy"),
        ("diabetes", "FOOD_AVOID", "Fried foods and trans fats", "Increase insulin resistance and cardiovascular risk"),
        ("diabetes", "WELLNESS_TIP", "Walk for 15-30 minutes after meals", "Post-meal walking can lower blood sugar by 20-40% naturally"),
        ("diabetes", "WELLNESS_TIP", "Check your feet daily for cuts, blisters, or swelling", "Diabetes reduces sensation — small wounds can become serious infections if unnoticed"),
        # Hypertension
        ("hypertension", "FOOD_RECOMMENDED", "Leafy greens (spinach, kale), berries, and oats", "Rich in potassium and nitrates that naturally relax blood vessels and lower pressure"),
        ("hypertension", "FOOD_RECOMMENDED", "Low-fat yogurt and bananas", "Calcium and potassium work together to regulate blood vessel tone"),
        ("hypertension", "FOOD_RECOMMENDED", "Garlic and beets", "Natural nitric oxide boosters that improve blood vessel flexibility"),
        ("hypertension", "FOOD_AVOID", "Pickles, soy sauce, and cured/deli meats", "Extremely high sodium causes your body to retain water, raising blood pressure"),
        ("hypertension", "FOOD_AVOID", "Excessive alcohol (more than 1 drink/day)", "Alcohol raises blood pressure and reduces effectiveness of BP medications"),
        ("hypertension", "WELLNESS_TIP", "Practice deep breathing for 5 minutes twice daily", "Slow breathing activates the parasympathetic nervous system and lowers BP by 5-10 mmHg"),
        ("hypertension", "WELLNESS_TIP", "Limit sodium to less than 2,300 mg per day", "Reducing salt is one of the most effective ways to lower blood pressure without medication"),
        # Asthma
        ("asthma", "FOOD_RECOMMENDED", "Fatty fish (salmon, mackerel), ginger, and turmeric", "Omega-3 and anti-inflammatory compounds help reduce airway swelling"),
        ("asthma", "FOOD_RECOMMENDED", "Apples and tomatoes", "Quercetin and lycopene act as natural antihistamines that ease breathing"),
        ("asthma", "FOOD_AVOID", "Sulfite-containing wines, dried fruits, and shrimp", "Sulfites trigger severe breathing difficulty in many asthma patients"),
        ("asthma", "FOOD_AVOID", "Cold drinks and ice cream during flare-ups", "Cold foods can trigger airway spasm and worsen symptoms"),
        ("asthma", "WELLNESS_TIP", "Keep a symptom diary to identify your personal triggers", "Common triggers include dust, pollen, cold air, and exercise — knowing yours helps prevent attacks"),
        ("asthma", "WELLNESS_TIP", "Always carry your rescue inhaler, even on good days", "Asthma attacks can happen unexpectedly — having your inhaler could save your life"),
        # Atrial Fibrillation
        ("atrial fibrillation", "FOOD_RECOMMENDED", "Consistent daily servings of green vegetables", "Keeping vitamin K intake STEADY (not high or low) prevents dangerous blood-thinning swings on Warfarin"),
        ("atrial fibrillation", "FOOD_RECOMMENDED", "Lean proteins and whole grains", "Heart-healthy foods that do not interfere with anticoagulant therapy"),
        ("atrial fibrillation", "FOOD_AVOID", "Cranberry juice and grapefruit", "These alter how your body processes Warfarin — can cause dangerous bleeding or clotting"),
        ("atrial fibrillation", "FOOD_AVOID", "Excessive alcohol and energy drinks", "Alcohol and caffeine are direct triggers for irregular heartbeat episodes"),
        ("atrial fibrillation", "WELLNESS_TIP", "Limit caffeine to 1-2 cups of coffee per day", "Caffeine stimulates the heart and can trigger palpitations and AF episodes"),
        ("atrial fibrillation", "WELLNESS_TIP", "Check your pulse daily for irregularity", "Catching rhythm changes early allows your doctor to adjust treatment before complications"),
    ]

    for keyword, category, item, rationale in dietary_seeds:
        cursor.execute("""
            INSERT OR IGNORE INTO dietary_guidelines (condition_keyword, category, item, rationale)
            VALUES (?, ?, ?, ?)
        """, (keyword, category, item, rationale))

    conn.commit()
    conn.close()
    print("Patient Portal migration complete: tables created, demo accounts seeded.")


if __name__ == "__main__":
    migrate_patient_portal()
