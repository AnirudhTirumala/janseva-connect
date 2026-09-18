export const ANDHRA_LOCATIONS = {
  'Alluri Sitharama Raju': ['Araku Valley', 'Chintapalle', 'Dumbriguda', 'Maredumilli', 'Paderu', 'Rampachodavaram'],
  Anakapalli: ['Anakapalle', 'Butchayyapeta', 'Chodavaram', 'Madugula', 'Narsipatnam', 'Yelamanchili'],
  Anantapuramu: ['Anantapur', 'Atmakur', 'Gooty', 'Kalyandurg', 'Raptadu', 'Tadipatri'],
  Annamayya: ['Madanapalle', 'Pileru', 'Rajampet', 'Rayachoti', 'Thamballapalle', 'Valmikipuram'],
  Bapatla: ['Addanki', 'Bapatla', 'Chirala', 'Parchur', 'Repalle', 'Vemuru'],
  Chittoor: ['Chittoor', 'Gangadhara Nellore', 'Gudipala', 'Kuppam', 'Palamaner', 'Puthalapattu'],
  'Dr. B.R. Ambedkar Konaseema': ['Alamuru', 'Amalapuram', 'Kothapeta', 'Mummidivaram', 'Ramachandrapuram', 'Razole'],
  'East Godavari': ['Anaparthi', 'Gokavaram', 'Kovvur', 'Nidadavole', 'Rajamahendravaram Rural', 'Rajamahendravaram Urban'],
  Eluru: ['Chintalapudi', 'Eluru', 'Jangareddygudem', 'Nuzvid', 'Polavaram', 'Tadepalligudem'],
  Guntur: ['Guntur', 'Mangalagiri', 'Pedakakani', 'Tadikonda', 'Tenali', 'Tullur'],
  Kakinada: ['Kakinada Rural', 'Kakinada Urban', 'Peddapuram', 'Pithapuram', 'Samalkota', 'Tuni'],
  Krishna: ['Avanigadda', 'Gudivada', 'Machilipatnam', 'Nandivada', 'Pamarru', 'Pedana'],
  Kurnool: ['Adoni', 'Alur', 'Kurnool', 'Nandikotkur', 'Pattikonda', 'Yemmiganur'],
  Nandyal: ['Allagadda', 'Atmakur', 'Banaganapalle', 'Dhone', 'Nandyal', 'Srisailam'],
  NTR: ['Gampalagudem', 'Jaggaiahpet', 'Mylavaram', 'Nandigama', 'Tiruvuru', 'Vijayawada Urban'],
  Palnadu: ['Gurazala', 'Macherla', 'Narasaraopet', 'Sattenapalle', 'Vinukonda', 'Pedakurapadu'],
  'Parvathipuram Manyam': ['Bobbili', 'Kurupam', 'Parvathipuram', 'Salur', 'Seethampeta', 'Veeraghattam'],
  Prakasam: ['Giddalur', 'Kanigiri', 'Kandukur', 'Markapuram', 'Ongole', 'Podili'],
  'Sri Potti Sriramulu Nellore': ['Atmakur', 'Kavali', 'Naidupeta', 'Nellore', 'Udayagiri', 'Venkatagiri'],
  'Sri Sathya Sai': ['Dharmavaram', 'Hindupur', 'Kadiri', 'Penukonda', 'Puttaparthi', 'Madakasira'],
  Srikakulam: ['Amadalavalasa', 'Ichchapuram', 'Palasa', 'Rajam', 'Srikakulam', 'Tekkali'],
  Tirupati: ['Chandragiri', 'Puttur', 'Renigunta', 'Srikalahasti', 'Sullurpeta', 'Tirupati Rural'],
  Visakhapatnam: ['Anandapuram', 'Bheemunipatnam', 'Gajuwaka', 'Pendurthi', 'Visakhapatnam Rural', 'Visakhapatnam Urban'],
  Vizianagaram: ['Bobbili', 'Cheepurupalli', 'Gajapathinagaram', 'Nellimarla', 'Vizianagaram', 'Srungavarapukota'],
  'West Godavari': ['Achanta', 'Bhimavaram', 'Narasapuram', 'Palakollu', 'Tanuku', 'Tadepalligudem'],
  'YSR Kadapa': ['Badvel', 'Jammalamadugu', 'Kadapa', 'Proddatur', 'Pulivendula', 'Yerraguntla'],
}

export const DISTRICTS = Object.keys(ANDHRA_LOCATIONS)

export const VILLAGES = ['Kakinada', 'Samalkota', 'Peddapuram', 'Rajamahendravaram', 'Amalapuram', 'Tuni', 'Vijayawada', 'Guntur', 'Tirupati', 'Visakhapatnam']

// Real village/town suggestions scoped to the selected mandal. Many AP
// mandals are named after their own headquarters town, so the mandal name
// itself is a genuine, verifiable place inside it; where the mandal name
// carries a "Rural"/"Urban" qualifier (e.g. "Kakinada Rural"), the
// underlying town name is offered too (e.g. "Kakinada"). This deliberately
// does not invent additional hamlet names that can't be verified - the
// field stays free text so a citizen can always type their actual village
// if it isn't one of these starting suggestions.
export function villageSuggestions(mandal) {
  if (!mandal) return VILLAGES
  const core = mandal.replace(/\s+(Rural|Urban)$/i, '')
  return core === mandal ? [mandal] : [mandal, core]
}
