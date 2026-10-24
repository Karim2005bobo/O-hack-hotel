"""Тестовые сценарии для замера качества агента.

Каждый сценарий — первое сообщение «как от живого человека», ответы на уточнения,
изменения условий по ходу и проверки итоговой брони.
"""

SCENARIOS = [
    {
        "name": "Море с ребёнком, недорого, без долгих перелётов",
        "messages": ["хочу куда-нибудь к тёплому морю в ноябре, недорого, с ребёнком, без долгих перелётов"],
        "answers": ["ребёнку 5 лет"],
        "checks": ["no_conn_errors", "max_flight", "kids_ok", "month"],
        "expect": {"max_flight_h": 5.5, "month": 11},
    },
    {
        "name": "Романтические выходные из Питера",
        "messages": ["Романтические выходные в городе с вкусной едой из Питера"],
        "checks": ["no_conn_errors", "origin"],
        "expect": {"origin": "LED"},
    },
    {
        "name": "Горы в июле с бюджетом",
        "messages": ["Горы и природа в июле, вдвоём, бюджет 150 тысяч"],
        "checks": ["no_conn_errors", "budget", "month"],
        "expect": {"budget": 150000, "month": 7},
    },
    {
        "name": "Конкретный город и праздники",
        "messages": ["На новогодние в Стамбул на 5 ночей из Казани"],
        "checks": ["no_conn_errors", "dest", "origin"],
        "expect": {"dest": ["istanbul"], "origin": "KZN"},
    },
    {
        "name": "С собакой на море поездом",
        "messages": ["Едем с собакой на море в сентябре, поездом, вдвоём"],
        "checks": ["no_conn_errors", "pets", "train"],
        "expect": {},
    },
    {
        "name": "Точные даты, семья, бюджет",
        "messages": ["с 10 по 17 ноября в Дубай, двое взрослых и двое детей 4 и 9 лет, до 400к"],
        "checks": ["no_conn_errors", "dest", "kids_ok", "budget"],
        "expect": {"dest": ["dubai"], "budget": 400000},
    },
    {
        "name": "Всё включено в Турции",
        "messages": ["хочу в Турцию всё включено первая линия, в июне, с мужем и дочкой 3 года"],
        "checks": ["no_conn_errors", "meal_ai", "kids_ok", "country_tr"],
        "expect": {},
    },
    {
        "name": "Пересборка: сдвиг дат",
        "messages": ["Хургада в декабре на неделю вдвоём"],
        "changes": ["а если на два дня позже?"],
        "checks": ["no_conn_errors", "dest", "replanned"],
        "expect": {"dest": ["hurghada"]},
    },
    {
        "name": "Пересборка: бюджет меньше",
        "messages": ["Шарм-эль-Шейх в январе, 2 взрослых, 4 звезды"],
        "changes": ["слишком дорого, бюджет меньше"],
        "checks": ["no_conn_errors", "dest", "replanned", "cheaper"],
        "expect": {"dest": ["sharm"]},
    },
    {
        "name": "Пересборка: с нами едет собака",
        "messages": ["Сочи в августе на неделю вдвоём"],
        "changes": ["с нами едет собака"],
        "checks": ["no_conn_errors", "pets", "replanned"],
        "expect": {"dest": ["sochi"]},
    },
    {
        "name": "Без визы, не Египет, февраль",
        "messages": ["не Египет, а что-то где можно купаться в феврале, без визы, нас двое"],
        "checks": ["no_conn_errors", "visa_free", "not_egypt"],
        "expect": {},
    },
    {
        "name": "Северное сияние",
        "messages": ["Хочу посмотреть северное сияние в январе на 4 ночи с подругой"],
        "checks": ["no_conn_errors", "dest"],
        "expect": {"dest": ["murmansk"]},
    },
    {
        "name": "Лыжи компанией из Новосибирска",
        "messages": ["кататься на лыжах в феврале, из Новосибирска, компанией из 4 человек"],
        "checks": ["no_conn_errors", "origin", "dest"],
        "expect": {"origin": "OVB", "dest": ["sheregesh", "rosa"]},
    },
    {
        "name": "Соло-путешествие, тусовки",
        "messages": ["я еду одна, хочу тусоваться и сёрфить, зимой, не дороже 200к"],
        "checks": ["no_conn_errors", "budget"],
        "expect": {"budget": 200000},
    },
    {
        "name": "Без пересадок, бюджет на человека",
        "messages": ["нас 4 человека, летим из Екатеринбурга в Анталью в июле, 70 000 на человека, только прямой рейс"],
        "checks": ["no_conn_errors", "direct", "dest", "budget"],
        "expect": {"dest": ["antalya"], "budget": 280000},
    },
    {
        "name": "Санаторий для мамы",
        "messages": ["отдых в санатории на минеральных водах в мае для мамы и меня"],
        "checks": ["no_conn_errors", "dest"],
        "expect": {"dest": ["kislovodsk"]},
    },
    {
        "name": "Размытый запрос без деталей",
        "messages": ["хочу отдохнуть"],
        "answers": ["в декабре, вдвоём"],
        "checks": ["no_conn_errors"],
        "expect": {},
    },
    {
        "name": "Поездом, боюсь летать",
        "messages": ["боюсь летать, хочу в Казань на выходные с женой"],
        "checks": ["no_conn_errors", "train", "dest"],
        "expect": {"dest": ["kazan"]},
    },
    {
        "name": "Малыш и Абхазия",
        "messages": ["Мы из Самары, хотим в Абхазию в июле на неделю, у нас малыш 1 год"],
        "checks": ["no_conn_errors", "origin", "dest", "kids_ok"],
        "expect": {"origin": "KUF", "dest": ["abkhazia"]},
    },
    {
        "name": "Медовый месяц, без ограничений",
        "messages": ["медовый месяц в марте, хотим что-то шикарное у океана на 10 ночей"],
        "checks": ["no_conn_errors"],
        "expect": {},
    },
    {
        "name": "Пересборка: длиннее и с животным в отель",
        "messages": ["Калининград в июле, 3 ночи, вдвоём"],
        "changes": ["на 2 дня дольше"],
        "checks": ["no_conn_errors", "dest", "replanned"],
        "expect": {"dest": ["kaliningrad"]},
    },
    {
        "name": "Детский отдых, аквапарк, бесплатная отмена",
        "messages": ["едем семьёй с детьми 6 и 10 лет, нужен аквапарк и бассейн, бесплатная отмена, в конце августа"],
        "checks": ["no_conn_errors", "kids_ok", "free_cancel"],
        "expect": {},
    },
]
