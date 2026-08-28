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
    'panel.character': 'Character',
    'panel.progress': 'Progress',
    'panel.search': 'Search',
    'panel.options': 'Options',
    'panel.selectNone': 'none',
    'panel.selectAll': 'all',
    'sb.collapse': 'Collapse sidebar',
    'sb.expand': 'Expand sidebar',
    'opt.hideFound': 'Hide found',
    'opt.showLabels': 'Show labels when zoomed',
    'opt.showIcons': "Use the game's map icons",

    'cat.grace': 'Sites of Grace',
    'cat.boss': 'Bosses',
    'cat.poi': 'Points of interest',
    'cat.region': 'Regions',
    'cat.fragment': 'Map fragments',
    'cat.landmark': 'Unnamed landmarks',
    'cat.armaments': 'Weapons, shields, bows, staves',
    'cat.armour': 'Armour',
    'cat.ashes_of_war': 'Ashes of War',
    'cat.spirits': 'Spirit Ashes',
    'cat.talismans': 'Talismans',
    'cat.celestial_dew': 'Celestial Dew',
    'cat.cookbooks': 'Cookbooks',
    'cat.crystal_tears': 'Crystal Tears',
    'cat.imbued_sword_keys': 'Imbued Sword Keys',
    'cat.larval_tears': 'Larval Tears',
    'cat.lost_ashes': 'Lost Ashes of War',
    'cat.pots_n_perfumes': 'Pots & Perfumes',
    'cat.seeds_tears': 'Golden Seeds & Sacred Tears',
    'cat.scadutree_fragments': 'Scadutree Fragments',
    'cat.whetblades': 'Whetblades',
    'cat.great_runes': 'Great Runes',
    'cat.ammo': 'Ammunition',
    'cat.bell_bearings': 'Bell Bearings',
    'cat.merchant_bell_bearings': 'Merchant Bell Bearings',
    'cat.consumables': 'Consumables',
    'cat.greases': 'Greases',
    'cat.utilities': 'Utility items',
    'cat.stat_boosts': 'Stat boosts',
    'cat.crafting_materials': 'Crafting materials',
    'cat.gloveworts': 'Gloveworts',
    'cat.great_gloveworts': 'Great Gloveworts',
    'cat.golden_runes': 'Golden Runes',
    'cat.golden_runes_low': 'Golden Runes (low)',
    'cat.material_nodes': 'Gathering nodes',
    'cat.mp_fingers': 'Multiplayer fingers',
    'cat.prattling_pates': 'Prattling Pates',
    'cat.gestures': 'Gestures',
    'cat.reusables': 'Reusable tools',
    'cat.smithing_stones': 'Smithing Stones',
    'cat.smithing_stones_low': 'Smithing Stones (low)',
    'cat.smithing_stones_rare': 'Smithing Stones (rare)',
    'cat.stonesword_keys': 'Stonesword Keys',
    'cat.throwables': 'Throwables',
    'cat.rune_arcs': 'Rune Arcs',
    'cat.dragon_hearts': 'Dragon Hearts',
    'cat.incantations': 'Incantations',
    'cat.memory_stones': 'Memory Stones',
    'cat.prayerbooks': 'Prayerbooks',
    'cat.sorceries': 'Sorceries',
    'cat.deathroot': 'Deathroot',
    'cat.progression': 'Quest items',
    'cat.seedbed_curses': 'Seedbed Curses',
    'cat.ember_pieces': 'Ember Pieces',
    'cat.items_and_changes': 'Added items',
    'cat.fortunes': 'Fortunes',
    'cat.rune_pieces': 'Rune Pieces',
    'cat.sealed_curios': 'Sealed Curios',
    'cat.misc': 'Other items',

    'master.M00': 'The Lands Between',
    'master.M01': 'Underground',
    'master.M10': 'Realm of Shadow',
    'master.M11': 'Realm of Shadow — Underground',

    'char.level': 'Level',
    'char.deaths': ['death', 'deaths', 'deaths'],
    'char.hoursShort': 'h',
    'char.minutesShort': 'm',
    'save.extension': 'Save type',
    'save.file': 'Save file',
    'save.account': 'Account',
    'save.switchFailed': 'Could not switch save',

    'popup.foundSave': '✓ Found — recorded in your save',
    'popup.foundManual': '✓ Marked found manually',
    'popup.notFound': 'Not found yet',
    'popup.mark': 'Mark as found',
    'popup.unmark': 'Unmark',
    'popup.close': 'Close',

    'label.height': 'Height',
    'unit.m': 'm',

    'tip.found': 'found',
    'tip.markers': ['marker', 'markers', 'markers'],
    'tip.clickZoom': 'click to zoom',

    'zoom.in': 'Zoom in',
    'zoom.out': 'Zoom out',
    'zoom.fit': 'Fit map',
    'zoom.player': 'Centre on your last save position',
    'zoom.noPlayer': 'Player position unavailable',
    'zoom.noPlayerSub': 'save has no readable position',
    'zoom.following': 'Following player — click to stop',

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
    'panel.character': 'Персонаж',
    'panel.progress': 'Прогресс',
    'panel.search': 'Поиск',
    'panel.options': 'Настройки',
    'panel.selectNone': 'снять',
    'panel.selectAll': 'все',
    'sb.collapse': 'Свернуть панель',
    'sb.expand': 'Развернуть панель',
    'opt.hideFound': 'Скрывать найденное',
    'opt.showLabels': 'Показывать названия при увеличении',
    'opt.showIcons': 'Использовать игровые значки',

    'cat.grace': 'Места благодати',
    'cat.boss': 'Боссы',
    'cat.poi': 'Точки интереса',
    'cat.region': 'Регионы',
    'cat.fragment': 'Фрагменты карты',
    'cat.landmark': 'Безымянные точки',
    'cat.armaments': 'Оружие, щиты, луки, посохи',
    'cat.armour': 'Доспехи',
    'cat.ashes_of_war': 'Пепел войны',
    'cat.spirits': 'Пепел призыва',
    'cat.talismans': 'Талисманы',
    'cat.celestial_dew': 'Небесная роса',
    'cat.cookbooks': 'Книги рецептов',
    'cat.crystal_tears': 'Хрустальные слёзы',
    'cat.imbued_sword_keys': 'Наполненные ключи-мечи',
    'cat.larval_tears': 'Слёзы личинки',
    'cat.lost_ashes': 'Утраченный пепел войны',
    'cat.pots_n_perfumes': 'Горшки и духи',
    'cat.seeds_tears': 'Золотые семена и священные слёзы',
    'cat.scadutree_fragments': 'Осколки Древа Тьмы',
    'cat.whetblades': 'Точильные клинки',
    'cat.great_runes': 'Великие руны',
    'cat.ammo': 'Боеприпасы',
    'cat.bell_bearings': 'Колокольные бубенцы',
    'cat.merchant_bell_bearings': 'Бубенцы торговцев',
    'cat.consumables': 'Расходники',
    'cat.greases': 'Смазки',
    'cat.utilities': 'Полезные предметы',
    'cat.stat_boosts': 'Усилители характеристик',
    'cat.crafting_materials': 'Материалы для крафта',
    'cat.gloveworts': 'Глоуворты',
    'cat.great_gloveworts': 'Великие глоуворты',
    'cat.golden_runes': 'Золотые руны',
    'cat.golden_runes_low': 'Золотые руны (слабые)',
    'cat.material_nodes': 'Точки сбора',
    'cat.mp_fingers': 'Мультиплеерные пальцы',
    'cat.prattling_pates': 'Болтливые куклы',
    'cat.gestures': 'Жесты',
    'cat.reusables': 'Многоразовые инструменты',
    'cat.smithing_stones': 'Кузнечные камни',
    'cat.smithing_stones_low': 'Кузнечные камни (слабые)',
    'cat.smithing_stones_rare': 'Кузнечные камни (редкие)',
    'cat.stonesword_keys': 'Камни-ключи',
    'cat.throwables': 'Метательные предметы',
    'cat.rune_arcs': 'Дуги рун',
    'cat.dragon_hearts': 'Сердца драконов',
    'cat.incantations': 'Заклинания',
    'cat.memory_stones': 'Камни памяти',
    'cat.prayerbooks': 'Молитвенники',
    'cat.sorceries': 'Чародейства',
    'cat.deathroot': 'Корень смерти',
    'cat.progression': 'Квестовые предметы',
    'cat.seedbed_curses': 'Проклятия ложа',
    'cat.ember_pieces': 'Осколки углей',
    'cat.items_and_changes': 'Добавленные предметы',
    'cat.fortunes': 'Амулеты удачи',
    'cat.rune_pieces': 'Осколки рун',
    'cat.sealed_curios': 'Запечатанные диковины',
    'cat.misc': 'Прочие предметы',

    'master.M00': 'Междуземье',
    'master.M01': 'Подземелья',
    'master.M10': 'Царство теней',
    'master.M11': 'Царство теней — подземелья',

    'char.level': 'Уровень',
    'char.deaths': ['смерть', 'смерти', 'смертей'],
    'char.hoursShort': 'ч',
    'char.minutesShort': 'м',
    'save.extension': 'Тип сохранения',
    'save.file': 'Файл сохранения',
    'save.account': 'Аккаунт',
    'save.switchFailed': 'Не удалось сменить сохранение',

    'popup.foundSave': '✓ Найдено — есть в сохранении',
    'popup.foundManual': '✓ Отмечено вручную',
    'popup.notFound': 'Ещё не найдено',
    'popup.mark': 'Отметить найденным',
    'popup.unmark': 'Снять отметку',
    'popup.close': 'Закрыть',

    'label.height': 'Высота',
    'unit.m': 'м',

    'tip.found': 'найдено',
    'tip.markers': ['метка', 'метки', 'меток'],
    'tip.clickZoom': 'нажмите, чтобы приблизить',

    'zoom.in': 'Приблизить',
    'zoom.out': 'Отдалить',
    'zoom.fit': 'Вся карта',
    'zoom.player': 'К позиции из последнего сохранения',
    'zoom.noPlayer': 'Позиция игрока недоступна',
    'zoom.noPlayerSub': 'в сохранении нет читаемой позиции',
    'zoom.following': 'Слежение за игроком — нажмите, чтобы остановить',

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
    this.listeners.forEach((listener) => { listener(lang); });
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
