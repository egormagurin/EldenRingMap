'use strict';
/**
 * UI localisation.
 *
 * Marker names do NOT live here — those come from the game's own message files
 * via data/markers.json, so a Site of Grace reads exactly as it does in-game.
 * This file only covers the chrome around the map.
 *
 * Where Elden Ring has an official Russian term, it is used verbatim:
 *   Sites of Grace   -> Места благодати   (GR_MenuText:241200)
 *   The Lands Between-> Междуземье
 *   Realm of Shadow  -> Царство теней     (PlaceName:8020000)
 *   Level            -> Уровень           (GR_MenuText:10200)
 */

const STRINGS = {
  en: {
    'app.subtitle': 'live map',
    'app.noSave': 'no save loaded',
    'app.noCharacter': 'No character',
    'app.noTiles': 'No map tiles found — run tools/extract_tiles.py',

    'live.on': 'live',
    'live.off': 'offline',
    'live.title': 'connection to the local server',

    'progress.overall': 'Overall',
    'search.placeholder': 'Search markers…',
    'search.none': 'no matches',

    'panel.map': 'Map',
    'panel.categories': 'Categories',
    'panel.selectNone': 'none',
    'panel.selectAll': 'all',
    'opt.hideFound': 'Hide found',
    'opt.showLabels': 'Show labels when zoomed',

    'cat.grace': 'Sites of Grace',
    'cat.boss': 'Bosses',
    'cat.poi': 'Points of interest',
    'cat.region': 'Regions',
    'cat.fragment': 'Map fragments',
    'cat.landmark': 'Unnamed landmarks',
    'cat.seed': 'Golden Seeds',
    'cat.tear': 'Sacred & Crystal Tears',
    'cat.talisman': 'Talismans',
    'cat.ash': 'Ashes of War',
    'cat.spirit': 'Spirit Ashes',
    'cat.cookbook': 'Cookbooks',
    'cat.bearing': 'Bell Bearings',
    'cat.whetblade': 'Whetblades',
    'cat.weapon': 'Weapons & shields',
    'cat.armor': 'Armour',
    'cat.misc': 'Other items',

    'master.M00': 'The Lands Between',
    'master.M01': 'Underground',
    'master.M10': 'Realm of Shadow',
    'master.M11': 'Realm of Shadow — Underground',

    'char.level': 'Level',
    'char.lastSave': 'Last save',
    'char.runes': 'runes',
    'char.deaths': ['death', 'deaths', 'deaths'],
    'char.hoursShort': 'h',
    'char.minutesShort': 'm',

    'popup.foundSave': '✓ Found — recorded in your save',
    'popup.foundManual': '✓ Marked found manually',
    'popup.notFound': 'Not found yet',
    'popup.mark': 'Mark as found',
    'popup.unmark': 'Unmark',
    'popup.close': 'Close',

    'tip.found': 'found',
    'tip.markers': ['marker', 'markers', 'markers'],
    'tip.clickZoom': 'click to zoom',

    'zoom.in': 'Zoom in',
    'zoom.out': 'Zoom out',
    'zoom.fit': 'Fit map',
    'zoom.player': 'Centre on your last save position',
    'zoom.noPlayer': 'Player position unavailable',
    'zoom.noPlayerSub': 'save has no readable position',

    'hint.controls': 'drag to pan · scroll to zoom',
    'foot.markers': 'markers',
    'foot.flagsAt': 'flags at',
    'err.parse': 'parse error',
    'err.saveRead': 'save read issue',
    'toast.discovered': 'discovered',
    'toast.more': 'more',
    'lang.label': 'Language',
    'live.realtime': 'real-time position',
    'live.waiting': 'waiting for the game',
    'live.denied': 'live reader needs administrator rights',
    'live.patched': 'live reader could not find the game structures',
  },

  ru: {
    'app.subtitle': 'живая карта',
    'app.noSave': 'сохранение не загружено',
    'app.noCharacter': 'Нет персонажа',
    'app.noTiles': 'Тайлы карты не найдены — запустите tools/extract_tiles.py',

    'live.on': 'на связи',
    'live.off': 'нет связи',
    'live.title': 'соединение с локальным сервером',

    'progress.overall': 'Всего',
    'search.placeholder': 'Поиск по меткам…',
    'search.none': 'ничего не найдено',

    'panel.map': 'Карта',
    'panel.categories': 'Категории',
    'panel.selectNone': 'снять',
    'panel.selectAll': 'все',
    'opt.hideFound': 'Скрывать найденное',
    'opt.showLabels': 'Показывать названия при увеличении',

    'cat.grace': 'Места благодати',
    'cat.boss': 'Боссы',
    'cat.poi': 'Точки интереса',
    'cat.region': 'Регионы',
    'cat.fragment': 'Фрагменты карты',
    'cat.landmark': 'Безымянные точки',
    'cat.seed': 'Золотые семена',
    'cat.tear': 'Священные и хрустальные слёзы',
    'cat.talisman': 'Талисманы',
    'cat.ash': 'Пепел войны',
    'cat.spirit': 'Пепел призыва',
    'cat.cookbook': 'Книги рецептов',
    'cat.bearing': 'Колокольные бубенцы',
    'cat.whetblade': 'Точильные клинки',
    'cat.weapon': 'Оружие и щиты',
    'cat.armor': 'Доспехи',
    'cat.misc': 'Прочие предметы',

    'master.M00': 'Междуземье',
    'master.M01': 'Подземелья',
    'master.M10': 'Царство теней',
    'master.M11': 'Царство теней — подземелья',

    'char.level': 'Уровень',
    'char.lastSave': 'Последнее сохранение',
    'char.runes': 'рун',
    'char.deaths': ['смерть', 'смерти', 'смертей'],
    'char.hoursShort': 'ч',
    'char.minutesShort': 'м',

    'popup.foundSave': '✓ Найдено — есть в сохранении',
    'popup.foundManual': '✓ Отмечено вручную',
    'popup.notFound': 'Ещё не найдено',
    'popup.mark': 'Отметить найденным',
    'popup.unmark': 'Снять отметку',
    'popup.close': 'Закрыть',

    'tip.found': 'найдено',
    'tip.markers': ['метка', 'метки', 'меток'],
    'tip.clickZoom': 'нажмите, чтобы приблизить',

    'zoom.in': 'Приблизить',
    'zoom.out': 'Отдалить',
    'zoom.fit': 'Вся карта',
    'zoom.player': 'К позиции из последнего сохранения',
    'zoom.noPlayer': 'Позиция игрока недоступна',
    'zoom.noPlayerSub': 'в сохранении нет читаемой позиции',

    'hint.controls': 'перетаскивайте — сдвиг · колесо — масштаб',
    'foot.markers': 'меток',
    'foot.flagsAt': 'флаги по',
    'err.parse': 'ошибка разбора',
    'err.saveRead': 'проблема чтения сохранения',
    'toast.discovered': 'открыто',
    'toast.more': 'ещё',
    'lang.label': 'Язык',
    'live.realtime': 'позиция в реальном времени',
    'live.waiting': 'ожидание игры',
    'live.denied': 'нужны права администратора',
    'live.patched': 'не удалось найти структуры игры',
  },
};

const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'ru', label: 'Русский' },
];

const I18n = {
  lang: 'en',
  listeners: [],

  init() {
    const saved = localStorage.getItem('er-map-lang');
    if (saved && STRINGS[saved]) this.lang = saved;
    else if ((navigator.language || '').toLowerCase().startsWith('ru')) this.lang = 'ru';
    document.documentElement.lang = this.lang;
    return this.lang;
  },

  set(lang) {
    if (!STRINGS[lang] || lang === this.lang) return;
    this.lang = lang;
    localStorage.setItem('er-map-lang', lang);
    document.documentElement.lang = lang;
    this.apply();
    this.listeners.forEach((f) => f(lang));
  },

  onChange(fn) { this.listeners.push(fn); },

  t(key) {
    const v = (STRINGS[this.lang] || {})[key];
    if (v !== undefined) return Array.isArray(v) ? v[2] : v;
    const en = STRINGS.en[key];
    return en === undefined ? key : (Array.isArray(en) ? en[2] : en);
  },

  /**
   * Count-aware lookup. Russian needs three forms (1 смерть / 2 смерти /
   * 5 смертей); English collapses to two, which the same table expresses.
   */
  plural(key, n) {
    const forms = (STRINGS[this.lang] || {})[key] || STRINGS.en[key];
    if (!Array.isArray(forms)) return this.t(key);
    if (this.lang === 'ru') {
      const m10 = n % 10, m100 = n % 100;
      if (m10 === 1 && m100 !== 11) return forms[0];
      if (m10 >= 2 && m10 <= 4 && !(m100 >= 12 && m100 <= 14)) return forms[1];
      return forms[2];
    }
    return n === 1 ? forms[0] : forms[1];
  },

  /** Marker name in the active language, falling back to English. */
  name(marker) {
    if (!marker) return '';
    if (marker.names) return marker.names[this.lang] || marker.names.en || '';
    return marker.name || '';
  },

  /** Rewrite every [data-i18n] node in the document. */
  apply() {
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = this.t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      el.title = this.t(el.dataset.i18nTitle);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.placeholder = this.t(el.dataset.i18nPlaceholder);
    });
  },
};

window.I18n = I18n;
window.I18N_LANGS = LANGS;
