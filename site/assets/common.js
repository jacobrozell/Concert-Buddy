/* Helpers shared by index.html and show.html. */
window.CB = (() => {
  const STATES = {AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',CO:'Colorado',CT:'Connecticut',DE:'Delaware',
    DC:'Washington, D.C.',FL:'Florida',GA:'Georgia',HI:'Hawaii',ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',KS:'Kansas',KY:'Kentucky',
    LA:'Louisiana',ME:'Maine',MD:'Maryland',MA:'Massachusetts',MI:'Michigan',MN:'Minnesota',MS:'Mississippi',MO:'Missouri',MT:'Montana',
    NE:'Nebraska',NV:'Nevada',NH:'New Hampshire',NJ:'New Jersey',NM:'New Mexico',NY:'New York',NC:'North Carolina',ND:'North Dakota',
    OH:'Ohio',OK:'Oklahoma',OR:'Oregon',PA:'Pennsylvania',RI:'Rhode Island',SC:'South Carolina',SD:'South Dakota',TN:'Tennessee',
    TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',WV:'West Virginia',WI:'Wisconsin',WY:'Wyoming'};
  // Stub paper colour = the state/region the show was in. Light papers so dark ink always reads.
  const KNOWN = {AL:'#f3a597',TN:'#a3dbc2',GA:'#c8b5ee',LA:'#f2d477',CO:'#97c9ec'};
  const EXTRA = ['#f5b8d6','#b9e3a0','#f7c59f','#a8d8e8','#e6c8a0','#d4c4f0','#f0b8b0','#c4e8d0','#e8e09a','#b8c8f0'];
  const DOW = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const MON = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const region = loc => (String(loc).split(',').pop() || '').trim();
  const regionName = r => STATES[r] || r;
  const paper = r => {
    if (KNOWN[r]) return KNOWN[r];
    let h = 0; for (const c of String(r)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
    return EXTRA[h % EXTRA.length];
  };
  const date = d => new Date(d + 'T12:00:00');
  const stubDate = d => { const x = date(d); return `${DOW[x.getDay()].slice(0,3).toUpperCase()} ${d.slice(5,7)}.${d.slice(8,10)}.${d.slice(2,4)}`; };
  const longDate = d => { const x = date(d); return `${DOW[x.getDay()]}, ${MON[x.getMonth()]} ${x.getDate()}, ${x.getFullYear()}`; };
  const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; };
  const clock = s => {
    if (s == null) return '';
    const h = Math.floor(s/3600), m = Math.floor(s%3600/60), sec = String(s%60).padStart(2,'0');
    return h ? `${h}:${String(m).padStart(2,'0')}:${sec}` : `${m}:${sec}`;
  };
  const getJSON = async url => { const r = await fetch(url, {cache:'no-cache'}); if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); };

  // Who you went with, from the companions column: 'Justin / Zach' -> ['Justin','Zach']; 'Solo' -> [] (same rules as build.py).
  const SOLO = ['solo', 'alone', 'just me', 'by myself', 'myself'];
  const isSolo = w => SOLO.includes(String(w || '').trim().toLowerCase());
  const people = w => isSolo(w) ? [] : String(w || '').split(/\s*\/\s*|\s*,\s*|\s+&\s+|\s+and\s+/).map(x => x.trim()).filter(Boolean);

  // True when previewing with `build.py --serve`; owner-only hints show only then.
  const local = ['localhost', '127.0.0.1', '[::1]', ''].includes(location.hostname);

  return {esc, region, regionName, paper, date, stubDate, longDate, today, clock, getJSON, local, isSolo, people};
})();
