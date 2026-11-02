# Lead CSV Cleaner — Hindi-English guide

## Mac par sample chalao

1. Project ZIP ko extract karo.
2. **Terminal** kholo. `cd ` likho (cd ke baad space), extracted project folder
   ko Terminal mein drag karo, phir **Enter** dabao.
3. Python check karo:

   ```bash
   python3 --version
   ```

   Version **3.10 ya newer** chahiye. Agar Python nahi mila, python.org se Python
   install karke Terminal dobara kholo.
4. Sample run karo:

   ```bash
   python3 -m lead_csv_cleaner examples/sample_leads.csv --output-dir reports/demo
   ```

   Result: **10 total, 5 clean, 3 review, 2 duplicates**.
5. Finder mein project ke andar **reports → demo** kholo. CSV files spreadsheet
   app mein khul jayengi.

## Apni CSV use karo

Project folder mein `data` folder banao. Apni UTF-8 CSV ko usmein `leads.csv`
naam se rakho. `company_name` aur `business_email` headers easiest hain.

```bash
python3 -m lead_csv_cleaner data/leads.csv --output-dir reports/my-first-list
```

- `clean_leads.csv`: required fields aur email-format check pass hua.
- `review.csv`: `_issues` column mein missing/invalid fields ka reason hai.
- `duplicates.csv`: same email dobara aaya; `_duplicate_of` original row batata hai.
- `summary.json`: total counts.

**Clean ka matlab deliverable ya qualified contact nahi hai.** Tool mailbox
existence, business purpose, country, ya ads budget verify nahi karta. Unknown
country blank hi rahegi. Kisi ko email nahi bhejta.

Dobara run karne ke liye naya output naam do, jaise `reports/my-second-list`.
Purani report overwrite nahi hoti. Original input file bhi unchanged rehti hai.

Country bhi required rakhni ho:

```bash
python3 -m lead_csv_cleaner data/leads.csv -o reports/with-country --require country
```

Windows par commands mein `python3` ki jagah `py -3` use karo.
