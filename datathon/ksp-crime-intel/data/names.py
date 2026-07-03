# names.py — Indian name parts + the "smudging" engine that makes records messy.
import random

FIRST_M = ["Suresh","Ramesh","Manjunath","Prakash","Ravi","Naveen","Kiran","Santosh",
    "Vijay","Anil","Mohammed","Imran","Basavaraj","Girish","Shivakumar","Nagaraj",
    "Harish","Umesh","Lokesh","Mahesh","Dinesh","Rajesh","Ganesh","Venkatesh",
    "Srinivas","Krishna","Raghavendra","Anand","Sunil","Praveen","Pavan","Chetan",
    "Darshan","Yogesh","Nithin","Sandeep","Vinay","Arun","Balaji","Chandru",
    "Devaraj","Eshwar","Gopal","Hanumantha","Jagadish","Karthik","Lohith","Madhu",
    "Nandish","Omkar","Puneeth","Ranganath","Sharath","Thimmaiah","Uday","Varun",
    "Waseem","Yashwanth","Zameer","Abdul","Farhan","Salman","Rizwan","Tanveer"]
FIRST_F = ["Lakshmi","Geetha","Sushma","Deepa","Ananya","Kavya","Reshma","Pooja",
    "Roopa","Shwetha","Ayesha","Fatima","Bhavya","Divya","Meena","Sunitha",
    "Anitha","Bharathi","Chaitra","Dhanya","Gayathri","Hemalatha","Indira","Jyothi",
    "Kalpana","Latha","Mamatha","Nandini","Padma","Rachana","Sahana","Tejaswini",
    "Uma","Vani","Yashoda","Akshata","Bindu","Chandana","Deepika","Gowramma",
    "Harini","Ishwarya","Kamala","Lalitha","Manjula","Netravati","Pallavi","Rekha",
    "Savitha","Triveni","Usha","Vidya","Zeenath","Noor","Sabiha","Ruksana"]
SURNAMES = ["Gowda","Reddy","Kumar","Naik","Hegde","Shetty","Patil","Rao","Kulkarni",
    "Desai","Sharma","Khan","Iyer","Murthy","Bhat","Rai","Acharya","Angadi","Badiger",
    "Bandi","Belagavi","Chavan","Devadiga","Doddamani","Gaonkar","Hadimani","Hiremath",
    "Jadhav","Kamath","Kattimani","Kodagu","Lamani","Madiwalar","Mallya","Mudaliar",
    "Nayaka","Pawar","Pujari","Salian","Shanbhag","Suvarna","Talawar","Uppar","Wali"]

# Common spelling variants used to "smudge" the same name across records.
VARIANTS = {
    "Mohammed": ["Mohammad","Muhammad","Mohamad","Md"],
    "Kumar":    ["Kumaar","Kumr"],
    "Reddy":    ["Reddi","Readdy"],
    "Gowda":    ["Gouda","Gowdaa"],
    "Shetty":   ["Setty","Shetti"],
    "Ayesha":   ["Aisha","Aysha"],
    "Lakshmi":  ["Laxmi","Lakshmy"],
}

def make_canonical(gender):
    first = random.choice(FIRST_M if gender == "M" else FIRST_F)
    surname = random.choice(SURNAMES)
    father = random.choice(FIRST_M)          # father's first name (same surname implied)
    return first, surname, father

def smudge(first, surname):
    """Corrupt a name the way real records do — but keep ~75% near-canonical
    so resolution is hard, not impossible."""
    f, s = first, surname
    r = random.random()
    if r < 0.75:                               # mostly written correctly
        return f"{f} {s}"
    ops = random.sample(["variant", "typo", "initial", "drop"], k=1)
    if "variant" in ops:
        if f in VARIANTS: f = random.choice(VARIANTS[f])
        if s in VARIANTS: s = random.choice(VARIANTS[s])
    if "typo" in ops and len(s) > 3:
        i = random.randint(1, len(s) - 2)
        s = s[:i] + s[i+1:]
    if "initial" in ops and len(f) > 1 and random.random() < 0.3:
        f = f[0] + "."
    if "drop" in ops and random.random() < 0.05:
        return f.strip()
    return f"{f} {s}".strip()
