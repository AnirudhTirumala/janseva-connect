from fastapi import APIRouter


router = APIRouter(prefix="/api/locations", tags=["Andhra Pradesh locations"])

# The district selector is intentionally canonical. Mandal/village inputs can
# remain flexible because they change more often and are maintained locally.
ANDHRA_PRADESH_DISTRICTS = [
    "Alluri Sitharama Raju", "Anakapalli", "Anantapuramu", "Annamayya", "Bapatla",
    "Chittoor", "Dr. B.R. Ambedkar Konaseema", "East Godavari", "Eluru", "Guntur",
    "Kakinada", "Krishna", "Kurnool", "Nandyal", "NTR", "Palnadu", "Parvathipuram Manyam",
    "Prakasam", "Sri Potti Sriramulu Nellore", "Sri Sathya Sai", "Srikakulam", "Tirupati",
    "Visakhapatnam", "Vizianagaram", "West Godavari", "YSR Kadapa",
]


@router.get("/districts")
def list_districts():
    return {"state": "Andhra Pradesh", "districts": ANDHRA_PRADESH_DISTRICTS}
