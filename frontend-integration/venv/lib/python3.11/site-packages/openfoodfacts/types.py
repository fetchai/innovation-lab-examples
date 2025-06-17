import enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, model_validator

#: A precise expectation of what mappings looks like in json.
#: (dict where keys are always of type `str`).
JSONType = Dict[str, Any]


class Flavor(str, enum.Enum):
    """Flavor is used to refer to a specific Open*Facts project:

    - Open Food Facts
    - Open Beauty Facts
    - Open Pet Food Facts
    - Open Product Facts
    - Open Food Facts (Pro plateform)
    """

    off = "off"
    obf = "obf"
    opff = "opff"
    opf = "opf"
    off_pro = "off-pro"

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name

    def get_base_domain(self) -> str:
        """Get the base domain (domain without TLD and without world/api
        subdomain) associated with the `Flavor`."""
        if self == self.off:
            return "openfoodfacts"
        elif self == self.obf:
            return "openbeautyfacts"
        elif self == self.opff:
            return "openpetfoodfacts"
        elif self == self.opf:
            return "openproductsfacts"
        else:
            # Open Food Facts Pro
            return "pro.openfoodfacts"

    @classmethod
    def get_from_server_domain(cls, server_domain: str) -> "Flavor":
        """Get the `Flavor` associated with a `server_domain`."""
        subdomain, base_domain, tld = server_domain.rsplit(".", maxsplit=2)

        if subdomain == "api.pro":
            if base_domain == "openfoodfacts":
                return cls.off_pro
            raise ValueError("pro platform is only available for Open Food Facts")

        for server_type in cls:
            if base_domain == server_type.get_base_domain():
                return server_type

        raise ValueError(f"no Flavor matched for server_domain {server_domain}")

    def is_food(self) -> bool:
        """Return True if the server type is `off` or `off-pro`, False
        otherwise."""
        return self in (self.off, self.off_pro)

    @classmethod
    def from_product_type(cls, product_type: str) -> "Flavor":
        """Get the `Flavor` associated with a `product_type`."""
        if product_type == "food":
            return Flavor.off
        elif product_type == "beauty":
            return Flavor.obf
        elif product_type == "petfood":
            return Flavor.opff
        elif product_type == "product":
            return Flavor.opf
        raise ValueError(f"no Flavor matched with product_type '{product_type}'")


class APIVersion(str, enum.Enum):
    v0 = "v0"
    v1 = "v1"
    v2 = "v2"
    v3 = "v3"


class Facet(str, enum.Enum):
    """An enum representing the facets available on Open Food Facts.

    The enum name is the singular form of the facet name, and the enum value is
    the plural form. Please note that we use underscores instead of dashes (as
    used in Open Food Facts API) in the enum name and value. The conversion
    will be performed automatically when using the API.
    """

    additive = "additives"
    allergen = "allergens"
    brand = "brands"
    category = "categories"
    country = "countries"
    contributor = "contributors"
    entry_date = "entry_dates"
    ingredient = "ingredients"
    label = "labels"
    language = "languages"
    nutrition_grade = "nutrition_grades"
    packaging = "packaging"
    packager_code = "packager_codes"
    purchase_place = "purchase_places"
    photographer = "photographers"
    informer = "informers"
    state = "states"
    store = "stores"
    trace = "traces"
    data_quality_warning = "data_quality_warnings"
    data_quality_error = "data_quality_errors"

    @classmethod
    def from_str_or_enum(cls, value: Union[str, "Facet"]) -> "Facet":
        """Convert a string to an enum value."""
        if isinstance(value, cls):
            return value

        elif isinstance(value, str):
            if value not in Facet.__members__:
                raise ValueError("unknown Facet: %s", value)
            return cls[value]


class Environment(str, enum.Enum):
    """Environment is used to specify Open Food Facts environment:

    - org: production (openfoodfacts.org)
    - net: staging (openfoodfacts.net)
    """

    org = "org"
    net = "net"


Country = enum.Enum(
    "Country",
    [
        ("af", "af"),
        ("ax", "ax"),
        ("al", "al"),
        ("dz", "dz"),
        ("as", "as"),
        ("ad", "ad"),
        ("ao", "ao"),
        ("ai", "ai"),
        ("aq", "aq"),
        ("ag", "ag"),
        ("ar", "ar"),
        ("am", "am"),
        ("aw", "aw"),
        ("au", "au"),
        ("at", "at"),
        ("az", "az"),
        ("bh", "bh"),
        ("bd", "bd"),
        ("bb", "bb"),
        ("by", "by"),
        ("be", "be"),
        ("bz", "bz"),
        ("bj", "bj"),
        ("bm", "bm"),
        ("bt", "bt"),
        ("bo", "bo"),
        ("ba", "ba"),
        ("bw", "bw"),
        ("bv", "bv"),
        ("br", "br"),
        ("io", "io"),
        ("vg", "vg"),
        ("bn", "bn"),
        ("bg", "bg"),
        ("bf", "bf"),
        ("bi", "bi"),
        ("kh", "kh"),
        ("cm", "cm"),
        ("ca", "ca"),
        ("cv", "cv"),
        ("bq", "bq"),
        ("ky", "ky"),
        ("cf", "cf"),
        ("td", "td"),
        ("cl", "cl"),
        ("cn", "cn"),
        ("cx", "cx"),
        ("cc", "cc"),
        ("co", "co"),
        ("km", "km"),
        ("ck", "ck"),
        ("cr", "cr"),
        ("ci", "ci"),
        ("hr", "hr"),
        ("cu", "cu"),
        ("cw", "cw"),
        ("cy", "cy"),
        ("cz", "cz"),
        ("cd", "cd"),
        ("dk", "dk"),
        ("dj", "dj"),
        ("dm", "dm"),
        ("do", "do"),
        ("ec", "ec"),
        ("eg", "eg"),
        ("sv", "sv"),
        ("gq", "gq"),
        ("er", "er"),
        ("ee", "ee"),
        ("et", "et"),
        ("fk", "fk"),
        ("fo", "fo"),
        ("fm", "fm"),
        ("fj", "fj"),
        ("fi", "fi"),
        ("fr", "fr"),
        ("gf", "gf"),
        ("pf", "pf"),
        ("tf", "tf"),
        ("ga", "ga"),
        ("gm", "gm"),
        ("ge", "ge"),
        ("de", "de"),
        ("gh", "gh"),
        ("gi", "gi"),
        ("gr", "gr"),
        ("gl", "gl"),
        ("gd", "gd"),
        ("gp", "gp"),
        ("gu", "gu"),
        ("gt", "gt"),
        ("gg", "gg"),
        ("gn", "gn"),
        ("gw", "gw"),
        ("gy", "gy"),
        ("ht", "ht"),
        ("hm", "hm"),
        ("hn", "hn"),
        ("hk", "hk"),
        ("hu", "hu"),
        ("is", "is"),
        ("in", "in"),
        ("id", "id"),
        ("ir", "ir"),
        ("iq", "iq"),
        ("ie", "ie"),
        ("im", "im"),
        ("il", "il"),
        ("it", "it"),
        ("jm", "jm"),
        ("jp", "jp"),
        ("je", "je"),
        ("jo", "jo"),
        ("kz", "kz"),
        ("ke", "ke"),
        ("ki", "ki"),
        ("xk", "xk"),
        ("kw", "kw"),
        ("kg", "kg"),
        ("la", "la"),
        ("lv", "lv"),
        ("lb", "lb"),
        ("ls", "ls"),
        ("lr", "lr"),
        ("ly", "ly"),
        ("li", "li"),
        ("lt", "lt"),
        ("lu", "lu"),
        ("mo", "mo"),
        ("mg", "mg"),
        ("mw", "mw"),
        ("my", "my"),
        ("mv", "mv"),
        ("ml", "ml"),
        ("mt", "mt"),
        ("mh", "mh"),
        ("mq", "mq"),
        ("mr", "mr"),
        ("mu", "mu"),
        ("yt", "yt"),
        ("mx", "mx"),
        ("md", "md"),
        ("mc", "mc"),
        ("mn", "mn"),
        ("me", "me"),
        ("ms", "ms"),
        ("ma", "ma"),
        ("mz", "mz"),
        ("mm", "mm"),
        ("na", "na"),
        ("nr", "nr"),
        ("np", "np"),
        ("nl", "nl"),
        ("nc", "nc"),
        ("nz", "nz"),
        ("ni", "ni"),
        ("ne", "ne"),
        ("ng", "ng"),
        ("nu", "nu"),
        ("nf", "nf"),
        ("kp", "kp"),
        ("mk", "mk"),
        ("mp", "mp"),
        ("no", "no"),
        ("om", "om"),
        ("pk", "pk"),
        ("pw", "pw"),
        ("pa", "pa"),
        ("pg", "pg"),
        ("py", "py"),
        ("pe", "pe"),
        ("ph", "ph"),
        ("pn", "pn"),
        ("pl", "pl"),
        ("pt", "pt"),
        ("pr", "pr"),
        ("qa", "qa"),
        ("cg", "cg"),
        ("re", "re"),
        ("ro", "ro"),
        ("ru", "ru"),
        ("rw", "rw"),
        ("bl", "bl"),
        ("sh", "sh"),
        ("kn", "kn"),
        ("lc", "lc"),
        ("mf", "mf"),
        ("pm", "pm"),
        ("vc", "vc"),
        ("ws", "ws"),
        ("sm", "sm"),
        ("st", "st"),
        ("sa", "sa"),
        ("sn", "sn"),
        ("rs", "rs"),
        ("sc", "sc"),
        ("sl", "sl"),
        ("sg", "sg"),
        ("sx", "sx"),
        ("sk", "sk"),
        ("si", "si"),
        ("sb", "sb"),
        ("so", "so"),
        ("za", "za"),
        ("gs", "gs"),
        ("kr", "kr"),
        ("ss", "ss"),
        ("es", "es"),
        ("lk", "lk"),
        ("ps", "ps"),
        ("sd", "sd"),
        ("sr", "sr"),
        ("sj", "sj"),
        ("sz", "sz"),
        ("se", "se"),
        ("ch", "ch"),
        ("sy", "sy"),
        ("tw", "tw"),
        ("tj", "tj"),
        ("tz", "tz"),
        ("th", "th"),
        ("bs", "bs"),
        ("tl", "tl"),
        ("tg", "tg"),
        ("tk", "tk"),
        ("to", "to"),
        ("tt", "tt"),
        ("tn", "tn"),
        ("tr", "tr"),
        ("tm", "tm"),
        ("tc", "tc"),
        ("tv", "tv"),
        ("ug", "ug"),
        ("ua", "ua"),
        ("ae", "ae"),
        ("uk", "uk"),
        ("us", "us"),
        ("um", "um"),
        ("uy", "uy"),
        ("uz", "uz"),
        ("vu", "vu"),
        ("va", "va"),
        ("ve", "ve"),
        ("vn", "vn"),
        ("vi", "vi"),
        ("wf", "wf"),
        ("eh", "eh"),
        ("ye", "ye"),
        ("yu", "yu"),
        ("zm", "zm"),
        ("zw", "zw"),
        ("world", "world"),
    ],
)

COUNTRY_CODE_TO_NAME = {
    Country["ao"]: "en:angola",
    Country["gh"]: "en:ghana",
    Country["mz"]: "en:mozambique",
    Country["kz"]: "en:kazakhstan",
    Country["kr"]: "en:south-korea",
    Country["am"]: "en:armenia",
    Country["bv"]: "en:bouvet-island",
    Country["ne"]: "en:niger",
    Country["mg"]: "en:madagascar",
    Country["ky"]: "en:cayman-islands",
    Country["yu"]: "en:yugoslavia",
    Country["mp"]: "en:northern-mariana-islands",
    Country["az"]: "en:azerbaijan",
    Country["nc"]: "en:new-caledonia",
    Country["cm"]: "en:cameroon",
    Country["gt"]: "en:guatemala",
    Country["tv"]: "en:tuvalu",
    Country["fi"]: "en:finland",
    Country["cr"]: "en:costa-rica",
    Country["dm"]: "en:dominica",
    Country["pk"]: "en:pakistan",
    Country["ml"]: "en:mali",
    Country["au"]: "en:australia",
    Country["np"]: "en:nepal",
    Country["vg"]: "en:british-virgin-islands",
    Country["ve"]: "en:venezuela",
    Country["fm"]: "en:federated-states-of-micronesia",
    Country["lk"]: "en:sri-lanka",
    Country["ci"]: "en:cote-d-ivoire",
    Country["za"]: "en:south-africa",
    Country["sa"]: "en:saudi-arabia",
    Country["ua"]: "en:ukraine",
    Country["ug"]: "en:uganda",
    Country["yt"]: "en:mayotte",
    Country["cy"]: "en:cyprus",
    Country["mr"]: "en:mauritania",
    Country["ru"]: "en:russia",
    Country["bm"]: "en:bermuda",
    Country["tz"]: "en:tanzania",
    Country["re"]: "en:reunion",
    Country["tc"]: "en:turks-and-caicos-islands",
    Country["vu"]: "en:vanuatu",
    Country["to"]: "en:tonga",
    Country["hu"]: "en:hungary",
    Country["bg"]: "en:bulgaria",
    Country["hk"]: "en:hong-kong",
    Country["pf"]: "en:french-polynesia",
    Country["al"]: "en:albania",
    Country["tl"]: "en:timor-leste",
    Country["mw"]: "en:malawi",
    Country["uk"]: "en:united-kingdom",
    Country["so"]: "en:somalia",
    Country["na"]: "en:namibia",
    Country["cu"]: "en:cuba",
    Country["bh"]: "en:bahrain",
    Country["bo"]: "en:bolivia",
    Country["sr"]: "en:suriname",
    Country["rs"]: "en:serbia",
    Country["mn"]: "en:mongolia",
    Country["ni"]: "en:nicaragua",
    Country["ir"]: "en:iran",
    Country["cg"]: "en:republic-of-the-congo",
    Country["ps"]: "en:state-of-palestine",
    Country["jp"]: "en:japan",
    Country["pg"]: "en:papua-new-guinea",
    Country["se"]: "en:sweden",
    Country["cv"]: "en:cape-verde",
    Country["pm"]: "en:saint-pierre-and-miquelon",
    Country["ee"]: "en:estonia",
    Country["sx"]: "en:sint-maarten",
    Country["li"]: "en:liechtenstein",
    Country["gr"]: "en:greece",
    Country["lu"]: "en:luxembourg",
    Country["fr"]: "en:france",
    Country["py"]: "en:paraguay",
    Country["ag"]: "en:antigua-and-barbuda",
    Country["ph"]: "en:philippines",
    Country["dk"]: "en:denmark",
    Country["gy"]: "en:guyana",
    Country["me"]: "en:montenegro",
    Country["mt"]: "en:malta",
    Country["ax"]: "en:aland-islands",
    Country["zw"]: "en:zimbabwe",
    Country["ca"]: "en:canada",
    Country["cn"]: "en:china",
    Country["io"]: "en:british-indian-ocean-territory",
    Country["bi"]: "en:burundi",
    Country["gl"]: "en:greenland",
    Country["gn"]: "en:guinea",
    Country["ck"]: "en:cook-islands",
    Country["pn"]: "en:pitcairn",
    Country["cz"]: "en:czech-republic",
    Country["bl"]: "en:saint-barthelemy",
    Country["lc"]: "en:saint-lucia",
    Country["ki"]: "en:kiribati",
    Country["kp"]: "en:north-korea",
    Country["sh"]: "en:saint-helena",
    Country["id"]: "en:indonesia",
    Country["bj"]: "en:benin",
    Country["mx"]: "en:mexico",
    Country["km"]: "en:comoros",
    Country["va"]: "en:vatican-city",
    Country["br"]: "en:brazil",
    Country["aw"]: "en:aruba",
    Country["lr"]: "en:liberia",
    Country["ke"]: "en:kenya",
    Country["cx"]: "en:christmas-island",
    Country["um"]: "en:united-states-minor-outlying-islands",
    Country["fj"]: "en:fiji",
    Country["fk"]: "en:falkland-islands",
    Country["no"]: "en:norway",
    Country["dz"]: "en:algeria",
    Country["la"]: "en:laos",
    Country["tg"]: "en:togo",
    Country["nr"]: "en:nauru",
    Country["si"]: "en:slovenia",
    Country["ec"]: "en:ecuador",
    Country["ga"]: "en:gabon",
    Country["uy"]: "en:uruguay",
    Country["il"]: "en:israel",
    Country["cw"]: "en:curacao",
    Country["mc"]: "en:monaco",
    Country["lv"]: "en:latvia",
    Country["td"]: "en:chad",
    Country["tw"]: "en:taiwan",
    Country["aq"]: "en:antarctic",
    Country["gg"]: "en:guernsey",
    Country["gi"]: "en:gibraltar",
    Country["tm"]: "en:turkmenistan",
    Country["gq"]: "en:equatorial-guinea",
    Country["nu"]: "en:niue",
    Country["pt"]: "en:portugal",
    Country["sn"]: "en:senegal",
    Country["gm"]: "en:gambia",
    Country["sg"]: "en:singapore",
    Country["tr"]: "en:turkey",
    Country["ye"]: "en:yemen",
    Country["im"]: "en:isle-of-man",
    Country["mh"]: "en:marshall-islands",
    Country["mo"]: "en:macau",
    Country["ge"]: "en:georgia",
    Country["mq"]: "en:martinique",
    Country["pr"]: "en:puerto-rico",
    Country["es"]: "en:spain",
    Country["it"]: "en:italy",
    Country["us"]: "en:united-states",
    Country["hm"]: "en:heard-island-and-mcdonald-islands",
    Country["md"]: "en:moldova",
    Country["vc"]: "en:saint-vincent-and-the-grenadines",
    Country["zm"]: "en:zambia",
    Country["xk"]: "en:kosovo",
    Country["ms"]: "en:montserrat",
    Country["tn"]: "en:tunisia",
    Country["cl"]: "en:chile",
    Country["co"]: "en:colombia",
    Country["cd"]: "en:democratic-republic-of-the-congo",
    Country["ch"]: "en:switzerland",
    Country["bn"]: "en:brunei",
    Country["ly"]: "en:libya",
    Country["kh"]: "en:cambodia",
    Country["tt"]: "en:trinidad-and-tobago",
    Country["ar"]: "en:argentina",
    Country["sj"]: "en:svalbard-and-jan-mayen",
    Country["in"]: "en:india",
    Country["cc"]: "en:cocos-keeling-islands",
    Country["nz"]: "en:new-zealand",
    Country["ht"]: "en:haiti",
    Country["st"]: "en:sao-tome-and-principe",
    Country["ws"]: "en:samoa",
    Country["bq"]: "en:caribbean-netherlands",
    Country["qa"]: "en:qatar",
    Country["mm"]: "en:myanmar",
    Country["sc"]: "en:seychelles",
    Country["gd"]: "en:grenada",
    Country["ba"]: "en:bosnia-and-herzegovina",
    Country["sl"]: "en:sierra-leone",
    Country["mf"]: "en:saint-martin",
    Country["bt"]: "en:bhutan",
    Country["kn"]: "en:saint-kitts-and-nevis",
    Country["is"]: "en:iceland",
    Country["tf"]: "en:french-southern-and-antarctic-lands",
    Country["eg"]: "en:egypt",
    Country["do"]: "en:dominican-republic",
    Country["th"]: "en:thailand",
    Country["nl"]: "en:netherlands",
    Country["vn"]: "en:vietnam",
    Country["pl"]: "en:poland",
    Country["eh"]: "en:western-sahara",
    Country["at"]: "en:austria",
    Country["gu"]: "en:guam",
    Country["er"]: "en:eritrea",
    Country["gp"]: "en:guadeloupe",
    Country["ng"]: "en:nigeria",
    Country["tj"]: "en:tajikistan",
    Country["gs"]: "en:south-georgia-and-the-south-sandwich-islands",
    Country["de"]: "en:germany",
    Country["mv"]: "en:maldives",
    Country["om"]: "en:oman",
    Country["lb"]: "en:lebanon",
    Country["ma"]: "en:morocco",
    Country["kg"]: "en:kyrgyzstan",
    Country["sm"]: "en:san-marino",
    Country["ae"]: "en:united-arab-emirates",
    Country["hr"]: "en:croatia",
    Country["tk"]: "en:tokelau",
    Country["pw"]: "en:palau",
    Country["dj"]: "en:djibouti",
    Country["sv"]: "en:el-salvador",
    Country["et"]: "en:ethiopia",
    Country["by"]: "en:belarus",
    Country["sb"]: "en:solomon-islands",
    Country["ro"]: "en:romania",
    Country["pe"]: "en:peru",
    Country["jo"]: "en:jordan",
    Country["fo"]: "en:faroe-islands",
    Country["uz"]: "en:uzbekistan",
    Country["my"]: "en:malaysia",
    Country["je"]: "en:jersey",
    Country["gf"]: "en:french-guiana",
    Country["ls"]: "en:lesotho",
    Country["rw"]: "en:rwanda",
    Country["sd"]: "en:sudan",
    Country["bs"]: "en:the-bahamas",
    Country["cf"]: "en:central-african-republic",
    Country["wf"]: "en:wallis-and-futuna",
    Country["ss"]: "en:south-sudan",
    Country["ad"]: "en:andorra",
    Country["bz"]: "en:belize",
    Country["vi"]: "en:virgin-islands-of-the-united-states",
    Country["gw"]: "en:guinea-bissau",
    Country["mk"]: "en:north-macedonia",
    Country["sk"]: "en:slovakia",
    Country["as"]: "en:american-samoa",
    Country["nf"]: "en:norfolk-island",
    Country["be"]: "en:belgium",
    Country["mu"]: "en:mauritius",
    Country["pa"]: "en:panama",
    Country["af"]: "en:afghanistan",
    Country["bf"]: "en:burkina-faso",
    Country["sy"]: "en:syria",
    Country["ai"]: "en:anguilla",
    Country["bd"]: "en:bangladesh",
    Country["kw"]: "en:kuwait",
    Country["bw"]: "en:botswana",
    Country["bb"]: "en:barbados",
    Country["iq"]: "en:iraq",
    Country["sz"]: "en:swaziland",
    Country["lt"]: "en:lithuania",
    Country["jm"]: "en:jamaica",
    Country["hn"]: "en:honduras",
    Country["world"]: "en:world",
    Country["ie"]: "en:ireland",
}

Lang = enum.Enum(
    "Lang",
    [
        ("cr", "cr"),
        ("bn", "bn"),
        ("rm", "rm"),
        ("kl", "kl"),
        ("en", "en"),
        ("tr", "tr"),
        ("el", "el"),
        ("or", "or"),
        ("lu", "lu"),
        ("xh", "xh"),
        ("so", "so"),
        ("zh", "zh"),
        ("ka", "ka"),
        ("sq", "sq"),
        ("pl", "pl"),
        ("et", "et"),
        ("ko", "ko"),
        ("nr", "nr"),
        ("es", "es"),
        ("ee", "ee"),
        ("ml", "ml"),
        ("cv", "cv"),
        ("la", "la"),
        ("rn", "rn"),
        ("tn", "tn"),
        ("an", "an"),
        ("vi", "vi"),
        ("ta", "ta"),
        ("is", "is"),
        ("fa", "fa"),
        ("bh", "bh"),
        ("ug", "ug"),
        ("ae", "ae"),
        ("ii", "ii"),
        ("rw", "rw"),
        ("lo", "lo"),
        ("wo", "wo"),
        ("sn", "sn"),
        ("sg", "sg"),
        ("sc", "sc"),
        ("de", "de"),
        ("ve", "ve"),
        ("eo", "eo"),
        ("id", "id"),
        ("ur", "ur"),
        ("to", "to"),
        ("sd", "sd"),
        ("nb", "nb"),
        ("ty", "ty"),
        ("ha", "ha"),
        ("km", "km"),
        ("ho", "ho"),
        ("tl", "tl"),
        ("ga", "ga"),
        ("kj", "kj"),
        ("xx", "xx"),
        ("mn", "mn"),
        ("se", "se"),
        ("hz", "hz"),
        ("as", "as"),
        ("tt", "tt"),
        ("mo", "mo"),
        ("fy", "fy"),
        ("ss", "ss"),
        ("gd", "gd"),
        ("ay", "ay"),
        ("ch", "ch"),
        ("zu", "zu"),
        ("be", "be"),
        ("bm", "bm"),
        ("vo", "vo"),
        ("aa", "aa"),
        ("mi", "mi"),
        ("ng", "ng"),
        ("hy", "hy"),
        ("jv", "jv"),
        ("yi", "yi"),
        ("mk", "mk"),
        ("dz", "dz"),
        ("fj", "fj"),
        ("lg", "lg"),
        ("cs", "cs"),
        ("om", "om"),
        ("cu", "cu"),
        ("sl", "sl"),
        ("st", "st"),
        ("oc", "oc"),
        ("ky", "ky"),
        ("da", "da"),
        ("mg", "mg"),
        ("ca", "ca"),
        ("os", "os"),
        ("it", "it"),
        ("ff", "ff"),
        ("ik", "ik"),
        ("bs", "bs"),
        ("sw", "sw"),
        ("bg", "bg"),
        ("fo", "fo"),
        ("ba", "ba"),
        ("pi", "pi"),
        ("dv", "dv"),
        ("uz", "uz"),
        ("hr", "hr"),
        ("lt", "lt"),
        ("no", "no"),
        ("kv", "kv"),
        ("bi", "bi"),
        ("nd", "nd"),
        ("co", "co"),
        ("li", "li"),
        ("sa", "sa"),
        ("ce", "ce"),
        ("ln", "ln"),
        ("nl", "nl"),
        ("ts", "ts"),
        ("ja", "ja"),
        ("kn", "kn"),
        ("ig", "ig"),
        ("ie", "ie"),
        ("hi", "hi"),
        ("tw", "tw"),
        ("gn", "gn"),
        ("mt", "mt"),
        ("gl", "gl"),
        ("kk", "kk"),
        ("ak", "ak"),
        ("fr", "fr"),
        ("br", "br"),
        ("qu", "qu"),
        ("sv", "sv"),
        ("gv", "gv"),
        ("av", "av"),
        ("tk", "tk"),
        ("sk", "sk"),
        ("kr", "kr"),
        ("ku", "ku"),
        ("te", "te"),
        ("ar", "ar"),
        ("mr", "mr"),
        ("su", "su"),
        ("cy", "cy"),
        ("na", "na"),
        ("ru", "ru"),
        ("ia", "ia"),
        ("ki", "ki"),
        ("iu", "iu"),
        ("za", "za"),
        ("uk", "uk"),
        ("lv", "lv"),
        ("kg", "kg"),
        ("ps", "ps"),
        ("ro", "ro"),
        ("af", "af"),
        ("sr", "sr"),
        ("sm", "sm"),
        ("az", "az"),
        ("he", "he"),
        ("my", "my"),
        ("nn", "nn"),
        ("hu", "hu"),
        ("gu", "gu"),
        ("eu", "eu"),
        ("si", "si"),
        ("ti", "ti"),
        ("th", "th"),
        ("ne", "ne"),
        ("pa", "pa"),
        ("bo", "bo"),
        ("nv", "nv"),
        ("oj", "oj"),
        ("ht", "ht"),
        ("yo", "yo"),
        ("ks", "ks"),
        ("fi", "fi"),
        ("io", "io"),
        ("ms", "ms"),
        ("lb", "lb"),
        ("kw", "kw"),
        ("ab", "ab"),
        ("tg", "tg"),
        ("am", "am"),
        ("mh", "mh"),
        ("ny", "ny"),
        ("pt", "pt"),
    ],
)


class APIConfig(BaseModel):
    user_agent: str
    country: Country = Country.world
    environment: Environment = Environment.org
    flavor: Flavor = Flavor.off
    version: APIVersion = APIVersion.v2
    username: Optional[str] = None
    password: Optional[str] = None
    session_cookie: Optional[str] = None
    timeout: float = 10.0

    @model_validator(mode="after")
    def check_credentials(self):
        """Check that username and password are provided together, and that
        either username/password or session_cookie is provided."""
        if (self.username and not self.password) or (
            self.password and not self.username
        ):
            raise ValueError("username and password must be provided together")

        if self.username and self.session_cookie:
            raise ValueError(
                "username/password and session_cookie are mutually exclusive"
            )

        return self

    @model_validator(mode="after")
    def check_user_agent(self):
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("User agent must be a string and cannot be empty.")
        return self


class DatasetType(str, enum.Enum):
    csv = "csv"
    jsonl = "jsonl"


class TaxonomyType(str, enum.Enum):
    category = "category"
    ingredient = "ingredient"
    label = "label"
    brand = "brand"
    packaging_shape = "packaging_shape"
    packaging_material = "packaging_material"
    packaging_recycling = "packaging_recycling"
    country = "country"
    nova_group = "nova_group"
    packaging = "packaging"
    additive = "additive"
    vitamin = "vitamin"
    mineral = "mineral"
    amino_acid = "amino_acid"
    nucleotide = "nucleotide"
    allergen = "allergen"
    state = "state"
    origin = "origin"
    language = "language"
    other_nutritional_substance = "other_nutritional_substance"
