import { ANDHRA_LOCATIONS, DISTRICTS, villageSuggestions } from '../data/andhraLocations'

export { DISTRICTS }

export default function LocationFields({ form, update }) {
  const control = 'w-full rounded-xl border border-ink/10 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-panchayat-500 focus:ring-4 focus:ring-panchayat-50'
  const mandals = ANDHRA_LOCATIONS[form.district] || []
  const villages = villageSuggestions(form.mandal)
  const changeDistrict = (event) => {
    update('district')(event)
    update('mandal')({ target: { value: '' } })
    update('village')({ target: { value: '' } })
  }
  const changeMandal = (event) => {
    update('mandal')(event)
    update('village')({ target: { value: '' } })
  }
  return <>
    <div>
      <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.1em] text-ink/55">District</label>
      <select required value={form.district || ''} onChange={changeDistrict} className={control}>
        <option value="">Select district</option>
        {DISTRICTS.map((district) => <option key={district} value={district}>{district}</option>)}
      </select>
    </div>
    <div>
      <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.1em] text-ink/55">Mandal</label>
      <select required disabled={!form.district} value={form.mandal || ''} onChange={changeMandal} className={`${control} disabled:cursor-not-allowed disabled:bg-ink/5`}>
        <option value="">{form.district ? 'Select mandal' : 'Select district first'}</option>
        {mandals.map((mandal) => <option key={mandal} value={mandal}>{mandal}</option>)}
      </select>
    </div>
    <div>
      <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.1em] text-ink/55">Town / village</label>
      <input required disabled={!form.mandal} list="ap-villages" value={form.village || ''} onChange={update('village')} placeholder={form.mandal ? 'Select or type your village/town' : 'Select mandal first'} className={`${control} disabled:cursor-not-allowed disabled:bg-ink/5`} />
      <p className="mt-1 text-[11px] text-ink/40">Pick a suggestion or type your exact village/town if it isn't listed.</p>
    </div>
    <datalist id="ap-villages">{villages.map((village) => <option key={village} value={village} />)}</datalist>
  </>
}
