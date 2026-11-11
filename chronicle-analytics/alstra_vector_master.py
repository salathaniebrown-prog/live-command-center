import os
import sys
import time
from astrapy import DataAPIClient
from astrapy.constants import VectorMetric
from astrapy.info import CollectionDefinition, CollectionVectorOptions, VectorServiceOptions
from astrapy.data_types import DataAPIDate

# --- INJECT LIVE CREDENTIAL ARRAYS FROM YOUR CLIPBOARD CACHE ---
ENDPOINT = "https://datastax.com"
TOKEN = os.getenv("ASTRA_DB_TOKEN", "")

def execute_ultimate_vector_suite():
    print("\n==================================================================")
    print(" 📡 ALSTRA VECTOR SUITE: INITIALIZING CORE OMEGA ENGINE LAYER     ")
    print("==================================================================")
    
    # 1. Establish Secure Cloud API Connection Handshake
    client = DataAPIClient()
    db = client.get_database(ENDPOINT, token=TOKEN)
    print(f"[SUCCESS] Remote handshake locked onto Astra DB: {db.info().name}")
    
    # 2. Provision or Access the Vector Space Collection Framework
    collection_name = "alstra_exoplanet_vectors"
    
    # Safely clear out any old workspace collections to guarantee clean states
    try:
        db.drop_collection(collection_name)
        print("[SANITIZATION] Flushed old vector collection sectors.")
    except:
        pass
        
    print("[SCHEMA] Building collection spine with NVIDIA nv-embedqa-e5-v5...")
    collection = db.create_collection(
        collection_name,
        definition=CollectionDefinition(
            vector=CollectionVectorOptions(
                metric=VectorMetric.COSINE,
                service=VectorServiceOptions(
                    provider="nvidia",
                    model_name="nvidia/nv-embedqa-e5-v5",
                ),
            )
        ),
    )
    print(f" -> Collection successfully verified: {collection.full_name}")
    
    # 3. Assemble and Structurally Map Document Payloads
    exoplanet_dataset = [
        {"title": "Kepler-1649 c", "author": "NASA Kepler", "rating": 4.9, "number_of_pages": 450, "genres": ["Habitable Earth Twin", "M-Dwarf Orbit", "Transit Detection"], "due_date": "2020-04-15", "summary": "An Earth-sized exoplanet orbiting within the habitable zone of a red dwarf star, blocking 14 percent flux."},
        {"title": "TOI-700 d", "author": "NASA TESS", "rating": 4.8, "number_of_pages": 520, "genres": ["Habitable Earth Twin", "Multi-Planet System", "Temperate Climate"], "due_date": "2020-01-06", "summary": "An Earth-sized world orbiting a stable host star with potential for liquid surface moisture metrics."},
        {"title": "Proxima Centauri b", "author": "ESO RV Team", "rating": 4.6, "number_of_pages": 380, "genres": ["Habitable Earth Twin", "Radial Velocity", "Closest System"], "due_date": "2016-08-24", "summary": "A close-proximity extrasolar planet orbiting within the liquid water boundaries of our nearest neighboring star system."},
        {"title": "LHS 1140 b", "author": "MEarth Project", "rating": 4.9, "number_of_pages": 610, "genres": ["Super-Earth", "Ocean World", "Thick Atmosphere"], "due_date": "2017-04-19", "summary": "A massive rocky ocean world candidate possessing a thick atmosphere and substantial water reservoirs."}
    ]
    
    documents = [
        {
            **data,
            "due_date": DataAPIDate.from_string(data["due_date"]) if data.get("due_date") else None,
            "$vectorize": f"summary: {data['summary']} | genres: {', '.join(data['genres'])}",
        }
        for data in exoplanet_dataset
    ]
    
    print("\n[INGESTION] Shipping structural vector rows to cloud cluster database...")
    inserted = collection.insert_many(documents)
    print(f" -> Success. Ingested {len(inserted.inserted_ids)} targets completely.")
    
    # 4. Execute Real-Time Semantic Vector Inversion Scans
    print("\n[ANALYTICS] Launching Query 1: Isolating High-Rank Targets (Rating > 4.7)...")
    rating_cursor = collection.find({"rating": {"$gt": 4.7}})
    for doc in rating_cursor:
        print(f"  ├── Target: {doc['title']} | Engine Rank Score: {doc['rating']}")
        
    print("\n[ANALYTICS] Launching Query 2: NVIDIA Semantic Search for 'A scary cold deep space world'...")
    single_match = collection.find_one(sort={"$vectorize": "A scary cold deep space world"})
    if single_match:
        print(f"  └── Nearest Target Match: {single_match['title']} [System Host: {single_match['author']}]")
        
    print("\n[ANALYTICS] Launching Query 3: Multi-Parameter Hybrid Vector Scan ('liquid ocean surface')...")
    vector_cursor = collection.find(
        {"number_of_pages": {"$gt": 400}},
        sort={"$vectorize": "A planet with a massive liquid water ocean surface layer"},
        limit=2,
        projection={"title": True, "author": True}
    )
    for doc in vector_cursor:
        print(f"  ├── Match Locked: {doc['title']} | Registry: {doc['author']}")
        
    print("==================================================================")
    print(" 🎉 PIPELINE RUN COMPLETE: VECTOR ENGINE DEPLOYED IN YOUR FAVOR  ")
    print("==================================================================\n")

if __name__ == "__main__":
    execute_ultimate_vector_suite()
