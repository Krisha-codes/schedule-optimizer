import { DAY_NAMES } from '../time.js'

export default function Controls({ settings, update }) {
  const toggleDay = (d) =>
    update({
      freeDays: settings.freeDays.includes(d)
        ? settings.freeDays.filter((x) => x !== d)
        : [...settings.freeDays, d],
    })

  return (
    <section className="card">
      <h2>Must-haves</h2>
      <p className="hint">Hard rules. A schedule that breaks one is never shown.</p>
      <div className="row">
        <label>
          No class before
          <input
            type="time"
            value={settings.earliest}
            onChange={(e) => update({ earliest: e.target.value })}
          />
        </label>
        <label>
          No class after
          <input
            type="time"
            value={settings.latest}
            onChange={(e) => update({ latest: e.target.value })}
          />
        </label>
      </div>
      <fieldset>
        <legend>Keep these days free</legend>
        {[0, 1, 2, 3, 4].map((d) => (
          <label key={d} className="check">
            <input
              type="checkbox"
              checked={settings.freeDays.includes(d)}
              onChange={() => toggleDay(d)}
            />
            {DAY_NAMES[d]}
          </label>
        ))}
      </fieldset>

      <h2>Preferences</h2>
      <p className="hint">Soft goals. Schedules that match them rank higher.</p>
      <div className="row">
        <label>
          I'd like to start after
          <input
            type="time"
            value={settings.prefStart}
            onChange={(e) => update({ prefStart: e.target.value })}
          />
        </label>
        <label>
          I'd like to finish by
          <input
            type="time"
            value={settings.prefEnd}
            onChange={(e) => update({ prefEnd: e.target.value })}
          />
        </label>
      </div>
      <label className="slider">
        <span>
          Fewer days on campus <b>{settings.wDays}</b>
        </span>
        <input
          type="range"
          min="0"
          max="200"
          step="10"
          value={settings.wDays}
          onChange={(e) => update({ wDays: Number(e.target.value) })}
        />
      </label>
      <label className="slider">
        <span>
          Shorter days, less waiting <b>{settings.wSpread}</b>
        </span>
        <input
          type="range"
          min="0"
          max="5"
          step="1"
          value={settings.wSpread}
          onChange={(e) => update({ wSpread: Number(e.target.value) })}
        />
      </label>
      <label>
        Variety between results
        <select
          value={settings.variety}
          onChange={(e) => update({ variety: Number(e.target.value) })}
        >
          <option value={1}>Low (similar is fine)</option>
          <option value={3}>Medium</option>
          <option value={5}>High</option>
        </select>
      </label>
    </section>
  )
}