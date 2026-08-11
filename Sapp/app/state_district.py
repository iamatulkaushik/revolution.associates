from django.db import models
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.forms import ModelForm
from django.core.validators import RegexValidator, EmailValidator, MinValueValidator, MaxValueValidator
from django.forms import forms
from django.forms import widgets, TextInput

class State(models.Model):
    Stateid = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    state_code = models.CharField(max_length=5, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        app_label = 'Sapp'
        db_table = "sa_states"
        verbose_name = "State"
        verbose_name_plural = "States"
    

class District(models.Model):
    Districtid = models.AutoField(primary_key=True)
    state = models.ForeignKey(State, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        app_label = 'Sapp'
        db_table = "sa_districts"
        verbose_name = "District"
        verbose_name_plural = "Districts"

class StateForm(ModelForm):
    class Meta:
        model = State
        fields = ['name', 'state_code']
        widgets = {
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter State Name'}),
            'state_code': TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter State Code'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise forms.ValidationError("State name cannot be empty.")
        return name

    def save(self, commit=True):
        state_instance = super().save(commit=False)
        if commit:
            state_instance.save()
        return state_instance


class DistrictForm(ModelForm):
    class Meta:
        model = District
        fields = ['state', 'name']
        widgets = {
            'state': widgets.Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter District Name'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise forms.ValidationError("District name cannot be empty.")
        return name

    def save(self, commit=True):
        district_instance = super().save(commit=False)
        if commit:
            district_instance.save()
        return district_instance

    @receiver(post_migrate)
    def create_default_states_and_districts(sender, app_config, **kwargs):
        try:
            StateModel = app_config.get_model('State')
            DistrictModel = app_config.get_model('District')
        except LookupError:
            return

        states_and_districts = {
            "andaman and nicobar islands": ["nicobar", "north and middle andaman", "south andaman"],
            "andhra pradesh": ["anantapur", "chittoor", "east godavari", "guntur", "krishna", "kurnool", "nellore", "prakasam", "srikakulam", "visakhapatnam", "vizianagaram", "west godavari"],
            "arunachal pradesh": ["anjaw", "changlang", "dibang valley", "east kameng", "east siang", "kurung kumey", "lepa rada", "lohit", "longding", "lower dibang valley", "lower subansiri", "namsai", "papum pare", "tawang", "tirap", "upper siang", "upper subansiri", "west kameng", "west siang"],
            "assam": ["baksa", "barpeta", "biswanath", "bongaigaon", "cachar", "charaideo", "chirang", "darrang", "dhemaji", "dhubri", "dibrugarh", "goalpara", "golaghat", "hailakandi", "jorhat", "kamrup metropolitan", "kamrup rural", "karbi anglong", "karimganj", "kokrajhar", "lakhimpur", "marigaon", "nagaon", "nalbari", "sivasagar", "sonitpur", "tinsukia", "udalguri"],
            "bihar": ["araria", "arwal", "aura", "banka", "begusarai", "bhagalpur", "bhojpur", "buxar", "darbhanga", "deo", "gaya", "gopalganj", "jamui", "jehanabad", "kaimur", "katihar", "khagaria", "kishanganj", "lakhisarai", "madhepura", "madhubani", "munger", "muzaffarpur", "nalanda", "nawada", "patna", "purnia", "rohtas", "saharsa", "samastipur", "saran", "sheikhpura", "sheohar", "sitamarhi", "siwan", "supaul", "vaishali"],
            "chandigarh": ["chandigarh"],
            "chhattisgarh": ["balod", "baloda bazar", "balrampur", "bastar", "bijapur", "bilaspur", "dantewada", "dhamtari", "durg", "gariaband", "janjgir-champa", "jashpur", "kabirdham", "kanker", "kondagaon", "korba", "korea", "mahasamund", "mungeli", "narayanpur", "raigarh", "raipur", "rajnandgaon", "sukma", "surajpur", "surguja"],
            "dadar and nagar haveli": ["dadar and nagar haveli"],
            "daman and diu": ["daman", "diu"],
            "delhi": ["central delhi", "east delhi", "new delhi", "north delhi", "north east delhi", "north west delhi", "shahdara", "south delhi", "south east delhi", "south west delhi", "west delhi"],
            "goa": ["north goa", "south goa"],
            "gujarat": ["ahmedabad", "amreli", "anand", "aravalli", "banas kantha", "bharuch", "bhavnagar", "botad", "chhota udepur", "dang", "devbhoomi dwarka", "gandhinagar", "gir somnath", "jamnagar", "junagadh", "kheda", "kutch", "mahesana", "morbi", "narmada", "navsari", "panchmahal", "patan", "porbandar", "rajkot", "sabarkantha", "surat", "surendranagar", "tapi", "vadodara", "valsad"],
            "haryana": ["ambala", "bhiwani", "charkhi dadri", "faridabad", "fatehabad", "gurugram", "hisar", "jhajjar", "jind", "kaithal", "karnal", "kurukshetra", "mahendragarh", "mewat", "palwal", "panchkula", "panipat", "rewari", "rohtak", "sirsa", "sonipat", "yamunanagar"],
            "himachal pradesh": ["bilaspur", "chamba", "hamirpur", "kangra", "kinnaur", "kullu", "lahaul and spiti", "mandi", "shimla", "sirmaur", "solan", "una"],
            "jammu and kashmir": ["anantnag", "bandipora", "baramulla", "budgam", "doda", "ganderbal", "jammu", "kathua", "kishtwar", "kulgam", "kupwara", "punch", "pulwama", "rajauri", "samba", "shopian", "srinagar", "udhampur"],
            "jharkhand": ["bokaro", "chatra", "deoghar", "dhanbad", "dumka", "east singhbhum", "garhwa", "giridih", "godda", "gumla", "hazaribagh", "jamtara", "khunti", "koderma", "latehar", "lohardaga", "pakur", "palamu", "ramgarh", "ranchi", "sahibganj", "sarai kala kharsawan", "simdega", "west singhbhum"],
            "karnataka": ["bagalkot", "ballari", "belagavi", "bengaluru rural", "bengaluru urban", "bidar", "chamarajanagar", "chikballapur", "chikkamagaluru", "chitradurga", "dakshina kannada", "davanagere", "dharwad", "gadag", "hassan", "haveri", "kodagu", "kolar", "kalaburagi", "mandya", "mysuru", "raichur", "ramanagara", "shivamogga", "tumakuru", "udupi", "uttara kannada"],
            "kerala": ["alappuzha", "ernakulam", "idukki", "kannur", "kasaragod", "kollam", "kottayam", "kozhikode", "malappuram", "palakkad", "pathanamthitta", "thiruvananthapuram", "thrissur", "wayanad"],
            "ladakh": ["kargil", "leh"],
            "lakshadweep": ["lakshadweep"],
            "madhya pradesh": ["agar malwa", "alirajpur", "anuppur", "ashoknagar", "balaghat", "barwani", "betul", "bhind", "bhopal", "burhanpur", "chhatarpur", "chhindwara", "damoh", "datia", "dewas", "dhar", "dindori", "guna", "guna", "harda", "hoshangabad", "indore", "jabalpur", "jhabua", "katni", "khandwa", "khargone", "mandla", "mandsaur", "morena", "narsinghpur", "neemuch", "panna", "raisen", "rajgarh", "ratlam", "rewa", "sagar", "satna", "sehore", "seoni", "shahdol", "shivpuri", "sidhi", "singrauli", "tikamgarh", "ujjain", "umaria", "vidisha"],
            "maharashtra": ["ahmednagar", "akola", "amravati", "aurangabad", "beed", "bhandara", "buldhana", "chandrapur", "dhule", "gadchiroli", "gondia", "hingoli", "jalgaon", "jalna", "kolhapur", "latur", "mumbai city", "mumbai suburban", "nagpur", "nandurbar", "nashik", "osmanabad", "parbhani", "pune", "raigad", "ratnagiri", "sangli", "satara", "solapur", "thane", "wardha", "washim", "yavatmal"],
            "manipur": ["bishnupur", "chandel", "churachandpur", "imphal east", "imphal west", "jangom", "kangpokpi", "noney", "senapati", "tamenglong", "tengnoupal", "thoubal", "ukhrul"],
            "meghalaya": ["east garo hills", "east jaintia hills", "east khasi hills", "north garo hills", "ri bawli", "south garo hills", "south west garo hills", "west garo hills", "west jaintia hills", "west khasi hills"],
            "mizoram": ["aizawl", "champhai", "kolasib", "lawngtlai", "lunglei", "mamit", "serchhip", "saitual", "hnahthial"],
            "nagaland": ["dimapur", "kiphire", "kohima", "longleng", "mokokchung", "mon", "peren", "phek", "tuensang", "wokha", "zunheboto"],
            "odisha": ["angul", "balangir", "balasore", "bargarh", "bhadrak", "boudh", "cuttack", "deogarh", "dhenkanal", "gajapati", "ganjam", "jagatsinghapur", "jajpur", "jharsuguda", "kalahandi", "kandhamal", "kendrapara", "kendujhar", "khordha", "koraput", "malkangiri", "mayurbhanj", "nabarangpur", "nayagarh", "nuapada", "puri", "rayagada", "sambalpur", "sundargarh"],
            "punjab": ["amritsar", "barnala", "bathinda", "faridkot", "fatehgarh sahib", "fazilka", "ferozepur", "gurdaspur", "hoshiarpur", "jalandhar", "kapurthala", "ludhiana", "mansa", "moga", "mohali", "pathankot", "patiala", "rupnagar", "sangrur", "shahid bhagat singh nagar", "tarn taran"],
            "rajasthan": ["ajmer", "alwar", "banswara", "baran", "barmer", "bharatpur", "bhilwara", "bikaner", "bundi", "chittorgarh", "churu", "dausa", "dholpur", "dungarpur", "hanumangarh", "jaipur", "jaisalmer", "jalore", "jhalawar", "jhunjhunu", "jodhpur", "karauli", "kota", "nagaur", "pali", "pratapgarh", "rajsamand", "sawai madhopur", "sikar", "sirohi", "tonk", "udaipur"],
            "sikkim": ["east sikkim", "north sikkim", "south sikkim", "west sikkim"],
            "tamil nadu": ["ariyalur", "chennai", "coimbatore", "cuddalore", "dharmapuri", "dindigul", "erode", "karur", "krishnagiri", "madurai", "nagapattinam", "namakkal", "perambalur", "pudukkottai", "ramanathapuram", "salem", "sivaganga", "thanjavur", "theni", "thoothukudi", "tiruchirappalli", "tirunelveli", "tiruppur", "tiruvallur", "tiruvannamalai", "tiruvarur", "vellore", "virudhunagar"],
            "telangana": ["adilabad", "bhadradri kothagudem", "hyderabad", "jagtial", "jangaon", "jayashankar bhupalpally", "jubilee hills", "kamareddy", "karimnagar", "khammam", "komaram bheem asifabad", "mahbubnagar", "medak", "medchal", "nagarkurnool", "nalgonda", "narayanpet", "nirmal", "nizamabad", "peddapalli", "rajanna sircilla", "rangareddy", "sangareddy", "siddipet", "suryapet", "vikarabad", "wanaparthy", "warangal rural", "warangal urban"],
            "tripura": ["dhalai", "gomati", "khowai", "north tripura", "sepahijala", "south tripura", "unakoti", "west tripura"],
            "uttar pradesh": ["agra", "aligarh", "ambedkar nagar", "amethi", "amroha", "aonla", "auraiya", "azamgarh", "baghpat", "bahraich", "ballia", "balrampur", "banda", "barabanki", "bareilly", "basti", "bhadohi", "bijnor", "bulandshahr", "chandauli", "chitrakoot", "deoria", "etah", "etawah", "faizabad", "farrukhabad", "fatehpur", "fikrabad", "gautam buddha nagar", "ghaziabad", "ghazipur", "gonda", "gorakhpur", "hamirpur", "hardoi", "hathras", "jalaun", "jaunpur", "jhansi", "kanpur dehat", "kanpur nagar", "kanshiram nagar", "kaushambi", "kheri", "lucknow", "maharajganj", "mahoba", "mainpuri", "mathura", "mau", "meerut", "mirzapur", "moradabad", "muzaffarnagar", "pilibhit", "pratapgarh", "rae bareli", "ramabai nagar", "rampur", "saharanpur", "sambhal", "shahjahanpur", "shamli", "siddharthnagar", "sitapur", "sonbhadra", "sultanpur", "unnao"],
            "uttarakhand": ["almora", "bageshwar", "chamoli", "champawat", "dehradun", "haridwar", "nainital", "pauri garhwal", "pitthoragarh", "rudraprayag", "tehri garhwal", "udham singh nagar", "uttarkashi"],
            "west bengal": ["alipurduar", "bankura", "basirhat", "birbhum", "cooch behar", "dakshin dinajpur", "darjeeling", "hooghly", "howrah", "jalpaiguri", "jhargram", "kalimpong", "kolkata", "malda", "murshidabad", "nadia", "north 24 parganas", "paschim medinipur", "purba medinipur", "purulia", "south 24 parganas", "uttar dinajpur"],
                    }

        for state_name, districts in states_and_districts.items():
            state_obj, created = StateModel.objects.get_or_create(name=state_name)
            for district_name in districts:
                DistrictModel.objects.get_or_create(state=state_obj, name=district_name)