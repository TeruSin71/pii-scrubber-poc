# Batch-path readability — union vs presidio

**Task 7 input. Batch path only: the KB text must stay readable, so an**
**extra redaction has a real cost here. On the live path it costs nothing.**

Ten samples: the seven with the most union over-redaction, then three with
none, for contrast. `over` lists spans covering no planted value, with the
engine whose span won the merge.

---

### 1. `HO-015` — holdout_samples.json

**original**

> PGI failing on plant 4000 deliveries since the morning batch window. No customer or personal data in this one - purely a movement type 601 configuration question.

**presidio**

> PGI failing on plant 4000 deliveries since the morning batch window. No customer or personal data in this one - purely a movement type 601 configuration question.

**both (union)**

> PGI failing on <ORG_NAME> <CUSTOMER_NO> deliveries since the morning batch window. No <PERSON> or personal data in this one - purely a movement type 601 configuration question.

over-redacted by union: `plant` (gliner/ORG_NAME), `4000` (gliner/CUSTOMER_NO), `customer` (gliner/PERSON)

---

### 2. `V3-003` — holdout_v3.json

**original**

> Raised by Søren Kjær (soren.kjaer@ourcompany.example) about Danish VAT determination on export orders to Norway.

**presidio**

> Raised by <PERSON> (<EMAIL>) about <ORG_NAME> <ORG_NAME> determination on export orders to <ADDRESS>.

**both (union)**

> Raised by <PERSON> (<EMAIL>) about <ORG_NAME> <ORG_NAME> determination on export orders to <ADDRESS>.

over-redacted by union: `Danish` (presidio/ORG_NAME), `VAT` (presidio/ORG_NAME), `Norway` (presidio/ADDRESS)

---

### 3. `TKT-0003` — samples.json

**original**

> Invoice IDoc failing in VF04 collective run. Bill-to customer 0001099233. Finance contact Meera Patel (meera.patel@globex.com) escalated; remittance IBAN NZ29 0011 2233 4455 6677 88 rejected by bank.

**presidio**

> <ORG_NAME> failing in VF04 collective run. <PERSON>-to customer <CUSTOMER_NO>. Finance contact <PERSON> (<EMAIL>) escalated; remittance IBAN <IBAN> rejected by bank.

**both (union)**

> <ORG_NAME> failing in VF04 collective run. <PERSON>-to customer <CUSTOMER_NO>. Finance contact <PERSON> (<EMAIL>) escalated; remittance IBAN <IBAN> rejected by bank.

over-redacted by union: `Invoice IDoc` (presidio/ORG_NAME), `Bill` (presidio/PERSON)

---

### 4. `HO-006` — holdout_samples.json

**original**

> ATP check timing out. Raised by Priyanka Sharma (priyanka.sharma@ourcompany.example), desk phone 04 803 5522, employee in the Wellington office at 22 Willis Street.

**presidio**

> ATP check timing out. Raised by <PERSON> (<EMAIL>), desk phone <PHONE>, employee in the <ADDRESS> office at <ADDRESS>

**both (union)**

> <ORG_NAME> check timing out. Raised by <PERSON> (<EMAIL>), desk phone <PHONE>, employee in the <ORG_NAME> at <ADDRESS>

over-redacted by union: `ATP` (gliner/ORG_NAME), `Wellington office` (gliner/ORG_NAME)

---

### 5. `HO-031` — holdout_samples.json

**original**

> Warehouse cannot print delivery notes at the Christchurch DC, 47 Halswell Junction Road. Site contact is the shift lead Mere Tuhoe on 03 344 7621. Printer queue ZLP_CHC01 shows 200 jobs.

**presidio**

> Warehouse cannot print delivery notes at <ORG_NAME>, <ADDRESS> Site contact is the shift lead Mere Tuhoe on <PHONE>. Printer queue ZLP_CHC01 shows 200 jobs.

**both (union)**

> <ORG_NAME> cannot print delivery notes at <ORG_NAME><ADDRESS> Site contact is the shift lead <PERSON> on <PHONE>. Printer queue ZLP_CHC01 shows 200 jobs.

over-redacted by union: `Warehouse` (gliner/ORG_NAME), `the ` (presidio/ORG_NAME)

---

### 6. `V2-064` — eval_samples_v2.json

**original**

> Movement type 601 posts against storage location 0001 for plant 4000, and there are 40 open transfer orders on the queue.

**presidio**

> Movement type 601 posts against storage location 0001 for plant 4000, and there are 40 open transfer orders on the queue.

**both (union)**

> Movement type 601 posts against <ADDRESS> for <ORG_NAME>, and there are 40 open transfer orders on the queue.

over-redacted by union: `storage location 0001` (gliner/ADDRESS), `plant 4000` (gliner/ORG_NAME)

---

### 7. `V3-020` — holdout_v3.json

**original**

> Redirect the pallet to 12 Kowhai Close, Tauranga 3110, the site office will sign between 8 and 4.

**presidio**

> Redirect the pallet to <ADDRESS>, the site office will sign between 8 and 4.

**both (union)**

> Redirect the pallet to <ADDRESS>, the <ORG_NAME> will sign between <PHONE>.

over-redacted by union: `site office` (gliner/ORG_NAME), `8 and 4` (gliner/PHONE)

---

### 8. `TKT-0001` — samples.json

**original**

> IDoc stuck in status 51 for sales order to customer 0001045567 (Harbour Freight Ltd). Error: 'ship-to party not found'. Reported by Aroha Ngata, aroha.ngata@harbourfreight.co.nz, ph +64 21 554 8890. Please advise.

**presidio**

> IDoc stuck in status 51 for sales order to customer <CUSTOMER_NO> (<ORG_NAME>). Error: 'ship-to party not found'. Reported by <PERSON>, <EMAIL>, ph <PHONE>. Please advise.

**both (union)**

> IDoc stuck in status 51 for sales order to customer <CUSTOMER_NO> (<ORG_NAME>). Error: 'ship-to party not found'. Reported by <PERSON>, <EMAIL>, ph <PHONE>. Please advise.

over-redacted by union: none

---

### 9. `TKT-0004` — samples.json

**original**

> CPI iFlow to endpoint 10.42.7.19 returning 500 on outbound delivery. Integration owner Tomasz Kowalski, tomasz.kowalski@acme-logistics.pl. Affects shipments for customer 0001200456.

**presidio**

> CPI iFlow to endpoint <IP_ADDRESS> returning 500 on outbound delivery. Integration owner <PERSON>, <EMAIL>. Affects shipments for customer <CUSTOMER_NO>.

**both (union)**

> CPI iFlow to endpoint <IP_ADDRESS> returning 500 on outbound delivery. Integration owner <PERSON>, <EMAIL>. Affects shipments for customer <CUSTOMER_NO>.

over-redacted by union: none

---

### 10. `TKT-0005` — samples.json

**original**

> Output type not triggering for order confirmation. NAST record missing. Requested by Sione Tuilagi from Pacific Traders, phone 09 445 2210, sione.t@pacifictraders.example.

**presidio**

> Output type not triggering for order confirmation. NAST record missing. Requested by <PERSON> from <ORG_NAME>, phone <PHONE>, <EMAIL>.

**both (union)**

> Output type not triggering for order confirmation. NAST record missing. Requested by <PERSON> from <ORG_NAME>, phone <PHONE>, <EMAIL>.

over-redacted by union: none

---
