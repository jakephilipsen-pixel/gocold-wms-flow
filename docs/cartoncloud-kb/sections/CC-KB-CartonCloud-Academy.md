# CartonCloud KB — CartonCloud Academy

_46 articles from the 'CartonCloud Academy' section of https://help.cartoncloud.com/knowledge._

## Contents

**CartonCloud Academy > TMS Basic Setup**

- [Delivery Runs in CartonCloud](#delivery-runs-in-cartoncloud)
- [Get Started with Custom Fields - Transport](#get-started-with-custom-fields-transport)
- [Get Started with Income Zone Sets](#get-started-with-income-zone-sets)
- [Get Started with Organisation Settings - Transport](#get-started-with-organisation-settings-transport)
- [Get Started with Parsers - Transport](#get-started-with-parsers-transport)
- [Get Started with Transport Lanes](#get-started-with-transport-lanes)
- [Get Started with Transport Zone Sets](#get-started-with-transport-zone-sets)
- [Introduction to CartonCloud's TMS](#introduction-to-cartonclouds-tms)
- [Introduction to Consignments](#introduction-to-consignments)
- [Introduction to Users in CartonCloud - Transport](#introduction-to-users-in-cartoncloud-transport-)
- [Learn about Customers - Transport](#learn-about-customers-transport)
- [Manifests in CartonCloud](#manifests-in-cartoncloud)
- [Run Sheets and Allocation in CartonCloud](#run-sheets-and-allocation-in-cartoncloud)
- [Transport Products in CartonCloud](#transport-products-in-cartoncloud)

**CartonCloud Academy > TMS Charging**

- [Charge Configurations](#charge-configurations)
- [Charging Methods](#charging-methods-academy)
- [Introduction to Transport Charging](#introduction-to-transport-charging)

**CartonCloud Academy > TMS Mobile App**

- [Delivering a Consignment and recording an electronic POD](#delivering-a-consignment-and-recording-an-electronic-pod)
- [Introducing the transport mobile app](#introducing-the-transport-mobile-app)
- [Learn about transport app features](#learn-about-transport-app-features)
- [Lodging a Consignment error](#lodging-a-consignment-error)
- [Scan Allocation](#scan-allocation-academy)

**CartonCloud Academy > WMS Basic Setup**

- [CartonCloud Inbound Process Explained](#cartoncloud-inbound-process-explained)
- [CartonCloud Outbound Process Explained](#cartoncloud-outbound-process-explained)
- [Get started with Organisation Settings - Warehouse](#get-started-with-organisation-settings-warehouse)
- [Get started with Parsers - Warehouse](#get-started-with-parsers-warehouse)
- [Introduction to Products Unit of Measure](#introduction-to-products-unit-of-measure)
- [Introduction to Users in CartonCloud - Warehouse](#introduction-to-users-in-cartoncloud-warehouse)
- [Introduction to WMS](#introduction-to-wms)
- [Learn about Customers - Warehouse](#learn-about-customers)
- [Learn about Warehouse Locations](#learn-about-warehouse-locations)
- [Products Explained](#products-explained)
- [Purchase Order Product Custom Fields Explained](#purchase-order-product-custom-fields-explained)
- [Setting up CartonCloud for WMS & TMS](#setting-up-cartoncloud-for-wms-tms)

**CartonCloud Academy > WMS Charging**

- [Introducing Warehouse Charging](#introducing-warehouse-charging)
- [Introduction to Handling Charges](#introduction-to-handling-charges)
- [Introduction to Storage Charges and Storage Periods](#introduction-to-storage-charges-and-storage-periods)
- [Other Charges](#other-charges)
- [Sale Order and Purchase Order Charges Explained](#sale-order-and-purchase-order-charges-explained)
- [Understanding Adhoc Charges](#understanding-adhoc-charges)
- [Understanding Storage Charge Methods](#understanding-storage-charge-methods)

**CartonCloud Academy > WMS Mobile App**

- [Introducing Scan Move](#introducing-scan-move)
- [Introducing the warehouse mobile app](#introducing-the-warehouse-mobile-app)
- [Introducing Wave Picking on the mobile app](#introducing-wave-picking-on-the-mobile-app)
- [Picking process on the mobile app (Sale Orders)](#picking-process-on-the-mobile-app-sale-orders)
- [Putaway process on the mobile app (Purchase Orders)](#putaway-process-on-the-mobile-app-purchase-orders)

---

# CartonCloud Academy > TMS Basic Setup

<a id="delivery-runs-in-cartoncloud"></a>
## Delivery Runs in CartonCloud

_Source: https://help.cartoncloud.com/knowledge/delivery-runs-in-cartoncloud_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Get Started with Custom Fields - Transport](https://help.cartoncloud.com/knowledge/get-started-with-custom-fields-transport) first.🎓

### What are Delivery Runs?

Delivery Runs in CartonCloud are the geographical boundaries of the places your operation delivers to.

For example, the map below shows the different areas on the Gold Coast that Coffee Warehousing and Distribution deliver to. When Nick creates his Delivery Runs in CartonCloud, he will create a Delivery Run for each of these areas.

**Map of different areas Coffee Warehousing and Distribution delivers to:**

**![](https://help.cartoncloud.com/hs-fs/hubfs/DR%201-png.png?width=247&height=459&name=DR%201-png.png)**

**Corresponding Delivery Runs in CartonCloud:**

**![](https://help.cartoncloud.com/hs-fs/hubfs/DR%202-png.png?width=670&height=255&name=DR%202-png.png)**

Follow along with Vincent as he gives you a brief overview of what a Delivery Run is (you can stop watching after timestamp 1:14)

**📹 Video:** https://www.youtube.com/embed/WjxKaLNaJ_A?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

### What are the benefits of Delivery Runs in CartonCloud?

Nick is super excited about using Delivery Runs in his operation as he will be able to break the Consignments into manageable quantities during allocation. This will enable an efficient and automatic allocation process in CartonCloud, meaning less manual work for Nick and his team!

CartonCloud will automatically allocate a Consignment to the appropriate Delivery Run depending on its pick-up location and delivery location. CartonCloud does this using the pickup location and delivery location on a Consignment (and the associated Transport Zone Set) to know what Delivery Run it needs to allocate it to. CartonCloud does this using address mapping and configurations you have set up on your Transport Lanes. Transport Lanes map the to and from address to the corresponding Delivery Run. Transport Lanes and Transport Zone Sets will be covered in later units; however, for now,  use the below diagram to understand better how the automatic allocation to a Delivery Run works.

![](https://help.cartoncloud.com/hs-fs/hubfs/DR%203-png.png?width=391&height=438&name=DR%203-png.png)

---

### Create a Delivery Run

Now that you know what a Delivery Run is, it is time to create them in your own CartonCloud account. Follow along with Vincent, as he explains what a Delivery Run is and how to add one to your account (if you watched the start of the video in the previous unit, you can skip to timestamp 1:14)

**📹 Video:** https://www.youtube.com/embed/WjxKaLNaJ_A?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

Nick now understands what a Delivery Run is and how to set them up in his CartonCloud account. All he needs to do is go ahead and create his Delivery Runs! If you already know what your Delivery Runs will be then we suggest you create one now. Otherwise, if you are still yet to determine what your Delivery Runs will be, you can come back to this unit later.

### Want to add more Delivery Runs?

If you already know what all your Delivery Runs will be, then you can create your Delivery Runs in bulk! To do so, you can use the export/import function. Follow the steps on the Knowledge Base page [How to add a Delivery Run](https://help.cartoncloud.com/x/bAeYHw) under the Export/Import Delivery Runs section.

### Want to add more Carriers?

A Carrier in CartonCloud is a transport carrier (for example a delivery, trucking or freight company) who delivers your transport jobs (Consignments). To create a Carrier, see [this](https://help.cartoncloud.com/x/hQG-I) page.

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Get Started with Transport Zone Sets](https://help.cartoncloud.com/knowledge/get-started-with-transport-zone-sets) 🎓

---

<a id="get-started-with-custom-fields-transport"></a>
## Get Started with Custom Fields - Transport

_Source: https://help.cartoncloud.com/knowledge/get-started-with-custom-fields-transport_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Learn about Customers - Transport](https://help.cartoncloud.com/knowledge/learn-about-customers-transport)first.🎓

#### What are Custom Fields?

Custom Fields allow you to record specific information against different records within CartonCloud. For example, you may want to record the Container Number against a Purchase Order or the delivery site opening hours against an address record. With CartonCloud’s Custom Fields, you are able to ensure all necessary data is recorded and available to the relevant users when required.

For example, Nick needs to record certain information against each Consignment (transport job), such as the service type, vehicle type and pallet type. He also wants the opening hours of the delivery address to be visible against the Consignment. In addition, for the jobs that Coffee Distribution and Warehousing don’t deliver and outsource to a third-party carrier, he wants to be able to record the price the carrier is charging against the job but doesn’t want the customer to be able to see the field. Nick would also like to record what driver accreditations each driver holds against the Driver in CartonCloud. These requirements that Nick has are all possible with Custom Fields!

**You can create Custom Fields for**

- Address
- Shipment
- Container
- Consignment Data
- Consignment Item
- Vehicle
- Customer
- Driver
- Sale Order
- Purchase Order
- Transport Product

**Examples of what you could use Custom Fields for (transport-specific)**

**Driver Custom Fields:**

- Dangerous Goods License
- Fatigue Accreditation
- Truck Safe Medical

**Consignment Data Custom Fields:**

- Vehicle Type (e.g. Tonne Truck, 4 Tonne, 6 Tonne, Semi etc.)
- Freight Type (e.g. Chiller, Frozen, Dry)
- Additional Reference (e.g. customer order number - the receiver's reference)
- Service Type (e.g. express)
- Pallet Type (e.g CHEP or Loscam)
- Dangerous Goods Type

**Address Custom Fields:**

- Opening Time
- Closing Time

Custom Fields can be made visible on the mobile app to make it easier for drivers to access key information such as the delivery locations opening hours. In addition, you can also choose to make the Custom Field not visible to the customer. This is great news for Nick from Coffee Distribution and Warehousing, as he can choose to hide the custom field containing the carrier's charges from his customers as this is sensitive information.

Watch the video below to find out how one of our customers uses custom fields to optimise their operations.

**📹 Video:** https://www.youtube.com/embed/kcLUIeHqMnk

Now that you know what a Custom Field is, it is time to have a go at creating one! Follow along with Vincent, as he shows you how to create a Custom Field.

**📹 Video:** https://www.youtube.com/embed/OQwFTxHm80g?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Get Started with Transport Zone Sets](https://help.cartoncloud.com/knowledge/get-started-with-transport-zone-sets) 🎓

---

<a id="get-started-with-income-zone-sets"></a>
## Get Started with Income Zone Sets

_Source: https://help.cartoncloud.com/knowledge/get-started-with-income-zone-sets_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Get Started with Transport Lanes](https://help.cartoncloud.com/knowledge/get-started-with-transport-lanes) first.🎓

In the previous units, we covered the components that enable CartonCloud to allocate Consignments automatically to a Delivery Run, creating a seamless and efficient allocation process for your operation.

Another way in which CartonCloud helps to optimise your processes and limit the number of manual tasks you and your team have to complete is by automatically calculating Consignment charges. CartonCloud uses Income Zone Sets, Rate Cards and Transport Rates to calculate Consignment charges automatically.

The below diagram helps to explain how this process works in CartonCloud.

![](https://help.cartoncloud.com/hs-fs/hubfs/IZS%201-png.png?width=670&height=503&name=IZS%201-png.png)

Rate Cards and Transport Rates will be covered in the TMS Charging Trail; therefore, in this unit, we will just focus on the role that Income Zone Sets play in the process.

### What are Income Zone Sets?

Income Zone Sets are similar to Transport Zone Sets; however, Income Zone Sets are the zones your operation uses for charging, whilst Transport Zones are the zones your operation uses for allocating Consignments.

Income Zones will be used when you create your Transport Rates and allow CartonCloud to calculate Consignment Charges automatically. Nick from Coffee Warehousing and Distribution is looking forward to setting up his Income Zones as it means he will no longer need to manually calculate Consignment charges, and the risk of revenue leakage will be significantly reduced.

Each Zone Set is made up of multiple zones, and each individual zone is made of single or multiple suburbs and postcodes. When creating zones, you can associate as many or as few suburbs and postcodes with one zone. This means you can create a zone for a state, city, area within a city, or even a specific suburb.

### Application of Income Zone Sets

For Coffee Warehousing and Distribution, they will need to create an Income Zone for each zone they use to base their rates off. For now, we will just focus on the Gold Coast area, but Nick will need to follow this process for all the areas the company deliver to. The map below shows how Coffee Warehousing and Distribution has divided the Gold Coast into different zones for its delivery allocation (Transport Zone Set) and rate calculation (Income Zone Set).

![](https://help.cartoncloud.com/hs-fs/hubfs/IZS%202-png.png?width=670&height=503&name=IZS%202-png.png)

Suppose Coffee Warehousing and Distribution have a consignment moving from Burleigh Heads to Paradise Point. In that case, CartonCloud will find the Income and Transport Zone associated with the suburbs of Burleigh Heads and Paradise Point.

![](https://help.cartoncloud.com/hs-fs/hubfs/IZS%203-png.png?width=670&height=503&name=IZS%203-png.png)

CartonCloud will then use the Income Zone pairing to find the associated Transport Rates and the Transport Zone pairing to find the matching Delivery Run.

**Consignment 1:**

- From address: CartonCloud, 5/27 Dover Drive, Burleigh Heads 4220
- To address : FoodWorks Paradise Point, Shop 1/3 Grice Avenue, Paradise Point 4216
- Income Zones: Area 2 → Area 1
- Transport Zones: GC Metro → GC North
- Delivery Run : Metro Daily

---

### Create an Income Zone Set

Now that you know what an Income Zone Set is, it is time to create one in your account.

Unlike Transport Zone Sets, where you can only have one Zone Set, you can have multiple Income Zone Sets. This is useful if you use different rating zones for different customers.

Coffee Warehousing and Distribution use two different charging zones in the Gold Coast area as they charge customers differently. In this case, Nick will need to create two different Income Zone Sets and associate the appropriate Zone Set to the correct Rate Card that the customer uses. For example, Coffee Warehousing and Distribution have two consignments for two different customers (Country Roasters and Coastal Coffee), both moving from the same address in Robina to the same address in Helensvale. Country Roaster’s Rate Card is associated with the Standard Income Zone Set, and Coastal Coffee’s Rate Card is associated with the Radius Income Zone Set (which is based on the distance from their depot).

Country Roaster’s consignment will travel from Area 2 to Area 1, whereas Coastal Coffee’s consignment will travel from Zone 1 to Zone 3. Therefore, even though both consignments have the same to and from address, the rates can be configured differently in accordance with the different Income Zone Sets.

![](https://help.cartoncloud.com/hs-fs/hubfs/IZS%204-png.png?width=670&height=503&name=IZS%204-png.png)

Follow along with Vincent as he further explains an Income Zone Set and how to set one up in your account.

**📹 Video:** https://www.youtube.com/embed/mQtFRiF_G-o

#### Need to create multiple zones?

If you know what Incomes Zones you need to create, then we suggest creating your Zones in bulk using the export/import function. To do this, please see [this](https://help.cartoncloud.com/x/j4bcI) page in our Knowledge Base (see the heading Creating zones in bulk - using the export/import function).

---

### Add and assign location entries

You have now created your Income Zones; however, CartonCloud still doesn’t know what Consignments need to be rated against each of these Zones. As of right now, these Zones have only been named; we haven’t defined the area associated with the zone (the postcode and suburb). This unit will cover how to define your zones by creating location entries.

### What is a location entry?

A location entry is a suburb and postcode combination associated with the relevant zone and used to find a match against addresses on Consignments. For example, even though we have created a zone called ‘Area 1’, CartonCloud still doesn’t know what Consignments need to be rated against ‘Area 1’. This is why you create location entries and associate the entry with the zone so that CartonCloud can associate the delivery address on the Consignment to the correct zone. So, for example, if you have a location entry for Burleigh within the Area 1 Income Zone, CartonCloud will now know that for any Consignments with a delivery address to Burleigh, they will be using the rates associated with the Area 1 Zone.

### Time to create a location entry!

To create your location entries, follow the instructions [here](https://help.cartoncloud.com/x/jYbcI). If you would like to create more than one location entry at a time, follow the instructions below.

To save time, you should create location entries using the export/import function. This is especially useful when you already have the locations stored in a spreadsheet format.

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Transport Products in CartonCloud](https://help.cartoncloud.com/knowledge/transport-products-in-cartoncloud)🎓

---

<a id="get-started-with-organisation-settings-transport"></a>
## Get Started with Organisation Settings - Transport

_Source: https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-transport_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Introduction to CartonCloud's TMS](https://help.cartoncloud.com/knowledge/introduction-to-cartonclouds-tms) first.🎓

### What are Organisation Settings?

The first step in your CartonCloud journey begins with setting up your Organisation Settings! Organisation Settings is like the control centre of your CartonCloud account; it allows you to customise and manage how you utilise CartonCloud within your operations.

There are a number of different settings within CartonCloud, which is great because it means you can easily adapt CartonCloud to meet your operational and customer needs. However, this means it is important that you understand the different types of settings and where to find them. We will cover settings throughout later pages; however, for now, let's focus on Organisation Settings.

**Organisation Settings** relate to your whole organisation. This means changes to Organisation Settings will apply to all your Customers and aspects of your CartonCloud account. The only way to override these settings is to make changes at the Customer Settings. Customer Settings will only apply to that applicable customer.

For example, Nick is the Manager at Coffee Distribution and Warehousing. Coffee Distribution and Warehousing store and deliver coffee beans for a number of different customers with varying operational needs. Nick is in charge of setting up CartonCloud for the company. He wants to know what type of settings he can set up in the Organisation Settings and the ones he needs to set up in the Customer Settings. He refers to the below table to better understand the difference.

| Organisation Settings | Customer Settings |
| --- | --- |
| Settings applied will apply to the entire organisation | Settings applied will only apply to that particular customer |
| You can override Organisation Settings using Customer Settings | You can not override Customer Settings; what you apply at the Customer level will override what you set up at the Organisation level |
| Your basic organisation information needs to be set up here (including logo) | Only customer-specific information will be set up here (customer address, phone number, etc) |
| Some settings in Organisation Settings can only be set up at the Organisation level | Some settings in Customer Settings can only be set up at the Customer level |

With Organisation and Customer Settings your options for meeting customer and operational needs are endless. We will cover Customer Settings in more detail in a later page. For now, we will focus on Organisation Settings.

We will be covering the following topics:

- Navigating the Organisation Settings
- First step...your Organisation's name
- Add your company branding
- Add your Organisation's address
- Set up your Warehouse

### Navigating the Organisation Settings

Let’s navigate to the Organisation Settings in your account.

- You can either select More > Organisation Settings or type Organisation Settings into the Search for anything! Box.
- You can move between each setting by utilising the tab headings at the top of the page.

Now, let’s start setting up your Organisation Settings! We will continue to use Nick from Coffee Warehousing and Distribution as our example. This is his first day setting up CartonCloud, so where should he start? To begin, Nick needs to update his company logo, name and address.

Follow along with Vincent, as he shows you how to set up your company logo, name and address from the Organisation Settings ***(only watch up to timestamp 4:00)***.

**📹 Video:** https://www.youtube.com/embed/PnWGiCcjSH4?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

### First step...your Organisation's name!

It’s time to add your organisation's name to CartonCloud. Let’s start by navigating to your Organisation Settings:

- Click the More tab in the top right corner.
- Select Organisation Settings .
- Click the Organisation tab.
- Enter your Organisation name in the Nickname field.
- You can also enter your Website , phone number and default currency .

![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Nov-19-2025-02-51-48-6819-AM.png?width=670&height=319&name=image-png-Nov-19-2025-02-51-48-6819-AM.png)

### Add your company branding!

Next, let’s add your company logo! From within the Organisation Settings:

- In the far right panel under Logo , click Upload Logo .

**![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Nov-19-2025-02-52-04-5229-AM.png?width=670&height=319&name=image-png-Nov-19-2025-02-52-04-5229-AM.png)**

- Select Choose File . Select your logo.
- Click, Upload Logo

### Add your Organisation's address

Now, it is time to add your Organisation’s address to CartonCloud, from within the Organisation Settings:

- Click the Address tab.
- Click Add New Address .

![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Nov-19-2025-02-53-35-0570-AM.png?width=670&height=325&name=image-png-Nov-19-2025-02-53-35-0570-AM.png)

- Search for your organisation in the Company name field. If it does not appear, fill in the address manually in the other address fields.
- Scroll down and click Add Address .
- Click Add New Address String . For more information on Address Strings click here .
- Enter your Organisation's name in the Address String name field.
- Select your Organisation's address from the Allocated to address drop down field.
- Click Add Address String . For more information on Address Strings, please click here .
- Enter the Default Latitude and Longitude (which will be shown in maps) if you wish.
- Scroll down and click Save .

Will you be using international addresses or are your operations based outside of Australia?

If you are using addresses outside of Australia or your operations are based outside of Australia, you will need to enable the **Allow International Addresses to be entered in CartonCloud**setting.

Nick knows that some of his customer's ship to New Zealand, so he will need to turn this setting on.

To turn this setting on (within the Organisation Settings):

- Select the Features & Options tab.
- Under Address Configuration , tick Allow International Addresses to be entered in CartonCloud
- Select your Default Country Address from the drop-down.
- Scroll down to the bottom of the page and select Save .

---

### Set up your Warehouse

Now that you have your basic Organisation Settings configured, you can set up your Warehouse. If you are only using the Transport Management System and don’t have a warehouse as such, you can think of this as your depot.

Nick knows Coffee Warehousing and Distribution have a warehouse in Sydney and also Melbourne. He will update the existing warehouse with the Sydney details and add another warehouse for the Melbourne warehouse.

Follow along with Vincent, as he sets up the Warehouse (watch from time stamp 4:00).

**📹 Video:** https://www.youtube.com/embed/PnWGiCcjSH4?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

*If you would like to add additional warehouses, please note that this will incur additional charges. Please contact your implementation consultant for more information.*

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Introduction to Users in CartonCloud - Transport](https://help.cartoncloud.com/knowledge/introduction-to-users-in-cartoncloud-transport-) 🎓

---

<a id="get-started-with-parsers-transport"></a>
## Get Started with Parsers - Transport

_Source: https://help.cartoncloud.com/knowledge/get-started-with-parsers-transport_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Run Sheets and Allocation in CartonCloud](https://help.cartoncloud.com/knowledge/run-sheets-and-allocation-in-cartoncloud) first.🎓

CartonCloud enables automated workflows and operational efficiencies, reducing admin and repetitive manual tasks, giving you and your team time back in your day for the important tasks. One way in which CartonCloud does this is through the use of Parsers.

### What are Parsers?

Parsers are able to read data and then import the data into CartonCloud in a format the system can understand. Using the data, the Parser can create or update a record in CartonCloud, for example, a Sale Order or Consignment.

Parsers are usually in the format of an excel spreadsheet (xlsx, csv etc.), and the document will contain all the data pertaining to the orders. There are three ways in which Parsers can be uploaded to CartonCloud:

1. Web application upload - from the ‘Parse a file’ page on the web app, the parser file can be uploaded directly to CartonCloud. The customers can also use the ‘Parse a file’ page from their customer login.
2. Email - the parser file can be uploaded via emailing the file to a set email address. Once emailed in, the orders will be automatically created in CartonCloud.
3. File Transfer Protocol (FTP) - for this method, please contact the CartonCloud team for more information.

### Benefits of using Parsers

- Eliminates repetitive data entry
- Reduces time spent creating/sending through orders for both your staff and your customers
- Data integrity - as the data only has to be entered once (as you can copy and paste the data into the file or use the file the data is already formatted in), you reduce the chances of error
- Reduce correspondence and admin time spent with the customer as they can email the order straight into CartonCloud, eliminating your involvement in the process

### Use cases for using Parsers

- If your customer has a large number of orders which need to be entered.
- If the data for the orders already exist in the format (for example, the software that generates the orders exports them in a CSV format)

### Types of Parsers

There are a number of different Parsers you can use with your CartonCloud account. This is great news for Nick from Coffee Warehousing and Distribution because he wants all his customers to send their orders in through email Parsers. This includes their Sale Orders and Purchase Orders.

One of Nick’s customers, Country Roasters, has invoices that need to be attached to each of their Sale Orders. Country Roasters doesn’t want to have to manually upload each invoice to the corresponding Sale Order in CartonCloud. Nick looks through the list of available Parsers and sees the Sale Order Invoice Parser. With this Parser, Country Roasters will be able to send through the invoice documents via email and they will automatically be uploaded and attached to the relevant Sale Order in CartonCloud. This works by scanning the uploaded document for the reference number and matching it against the Sale Order it is to be attached to.

Please see the list of available Parsers [here](https://help.cartoncloud.com/help/s/article/List-of-Parsers).

---

### How to set your Customer up with Parsers

Now that you know what a Parser is and the benefits they bring to you and your Customer’s operations it is time to learn how to set your Customer’s up with Parsers.

Nick knows that Country Roasters will be using Parsers to send through their Purchase Orders and Sale Orders. Country Roasters have requested that they email the file in. Nick knows this is possible with CartonCloud, so he downloads the default Purchase Order and Sale Order parser template to send them. He also mentions to them that if they require other fields to be parsed in or would like a custom template, the CartonCloud team can set this up at a cost.

Before Nick sends the template to Country Roasters, he needs to configure the particular Parsers to the customer. Follow along with Vincent as he steps through the process of configuring a Parser to the Customer.

**📹 Video:** https://www.youtube.com/embed/pZyNrDOD7yk?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

---

### Parsers in action

Now that you know what a Parser is and how to set them up for your Customers it is time to cover how to use the Parsers!

### Ways to upload a Parser

As covered in the first unit, there are three ways Parsers can be uploaded to CartonCloud.

1. Web application upload - from the ‘Parse a file’ page on the web app, the parser file can be uploaded directly to CartonCloud. The customers can also use the ‘Parse a file’ page from their customer login.
2. Email - the parser file can be uploaded via emailing the file to a set email address. Once emailed in, the orders will be automatically created in CartonCloud.
3. File Transfer Protocol (FTP ) - Please contact the CartonCloud team for more information on this method.

We will cover web upload and email in this unit. For information on File Transfer Protocol (FTP), please [contact the CartonCloud team](https://support.cartoncloud.com/servicedesk/customer/portal/2/user/login?destination=portal%2F2).

This is great for Nick as he can offer his customers options on how they wish to send through their orders, making the order creation process flexible and adaptable to best meet their operational workflows.

Parsers are not only limited to customers. Nick and his team will also be able to use Parsers and both upload methods if required. This is helpful if a customer cannot upload their orders or there were mistakes with the original orders, and the orders need to be deleted and uploaded again.

### Web upload (‘Parse a file’)

You can upload Parsers through the web app using the ‘Parse a file’ page in CartonCloud. This page is accessible for both Administrator and Customer user roles.

You will need to ensure you have followed the steps in the ‘How to set your Customer up with Parsers’ unit for your customers to be able to upload Parsers through the web application. If you have not completed this step, please go back to this unit or see [this](https://help.cartoncloud.com/x/GAK_Hw) page for steps to set up your customer with the Parser.

**Steps to upload a Parser using the ‘Parse a file’ page**

You will need to ensure you have downloaded the template associated with the Parsers and use this template to fill in your order data. Once you have filled in the template, you will upload this file to CartonCloud.

**(1) Download the template**

- Navigate to the relevant Parser by typing Parsers into the Search for anything bar. Click View against the relevant Parser.
- Click Download .
- Alternatively, you can use this page to download the relevant file.

**(2) Parse the file**

- Navigate to the Parse a file page, More > Parse a file .
- Select the Customer you wish to parse the file for.
- Select the relevant Parser.
- Select the file.
- Select if you wish to send an import email to the customer.
- Click Upload .

### Emailing in Parsers

The second option is to email the file into CartonCloud. This is an efficient and effective workflow for your customers as they can upload their orders in one simple step! They won’t even need to be logged in to CartonCloud.

To do this, you will need to ensure you have followed the steps in the ‘How to set your Customer up with Parsers’ unit for your customers to be able to email Parsers through to CartonCloud. If you have not completed this step, please go back to this unit or see [this](https://help.cartoncloud.com/x/GAK_Hw) page for steps to set up your customer with the Parser.

Follow along with Vincent as he shows you how to email a Parser into CartonCloud. Watch the video from timestamp 5:43.

**📹 Video:** https://www.youtube.com/embed/pZyNrDOD7yk?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Manifests in CartonCloud](https://help.cartoncloud.com/knowledge/manifests-in-cartoncloud) [/knowledge/cartoncloud-inbound-process-explained](https://help.cartoncloud.com/knowledge/cartoncloud-inbound-process-explained)[🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="get-started-with-transport-lanes"></a>
## Get Started with Transport Lanes

_Source: https://help.cartoncloud.com/knowledge/get-started-with-transport-lanes_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Get Started with Transport Zone Sets](https://help.cartoncloud.com/knowledge/get-started-with-transport-zone-sets)first.🎓

Transport Lanes are the last piece in the puzzle for setting up CaronCloud to automatically allocate Consignments to a Delivery Run!

### What are Transport Lanes?

Transport Lanes contain the logic and rules that dictate what Delivery Run a consignment is assigned to. Defining this logic in the Transport Lane enables CartonCloud to automatically assign consignments to the appropriate Delivery Run. The logic is defined using your [Transport Zone Set](https://help.cartoncloud.com/x/wILcI) (the defined geographical zones your operation delivers to) and your [Delivery Runs](https://help.cartoncloud.com/display/KB2/Delivery+Runs) (how you operationally group your consignments for allocating activities to drivers and vehicles).

### Application of Transport Lanes

To understand how Transport Lanes work in CartonCloud, we will use an example delivery Consignment for Coffee Warehousing and Distribution. This Consignment is moving from Burleigh Heads to Paradise Point. And for this example, we will assume Nick has already created his Transport Lane that specified that any delivery Consignment moving from the GC Metro Zone (Transport Zone) must be assigned to the ‘Metro Daily’ Delivery Run.

Using the logic you define in the Transport Lane, CartonCloud will match the Consignmets to and from Transport Zone to the corresponding Delivery Run.

### How CartonCloud automatically assigns the Consignment to a Delivery Run

![](https://help.cartoncloud.com/hs-fs/hubfs/TL%201-png.png?width=1536&height=1152&name=TL%201-png.png)

**Coffee Warehousing and Distribution Consignment example:**

**![](https://help.cartoncloud.com/hs-fs/hubfs/TL%202-png.png?width=1536&height=1152&name=TL%202-png.png)**

---

### Add and configure a Transport Lane

Now that you know what a Transport Lane is and its important role in automatically allowing CartonCloud to allocate Consignments to a Delivery Run, it is time to start creating your Transport Lanes!

If you don’t know what Transport Lanes you need to create, we recommend you still follow along and create a Transport Lane that you can edit later.

Follow along with Vincent as he explains what a Transport Lane is, how to add one and how to configure the Transport Lane to ensure the correct Consignments are allocated to the right Delivery Run.

**📹 Video:** https://www.youtube.com/embed/5cUG8aiQiek?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

Nick from Coffee Warehousing and Distribution is excited to start creating his Transport Lanes and for CartonCloud to automatically allocate Consignments to their correct Delivery Run. This will save Nick and his team a lot of time and reduce the manual work required during the allocation process.

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Get Started with Income Zone Sets](https://help.cartoncloud.com/knowledge/get-started-with-income-zone-sets) 🎓

---

<a id="get-started-with-transport-zone-sets"></a>
## Get Started with Transport Zone Sets

_Source: https://help.cartoncloud.com/knowledge/get-started-with-transport-zone-sets_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Delivery Runs in CartonCloud](https://help.cartoncloud.com/knowledge/delivery-runs-in-cartoncloud) first.🎓

### What is a Transport Zone Set?

Transport Zone Sets are defined geographical areas your operation uses for allocating deliveries. Transport Zone Sets and Transport Lanes work together to provide the framework and logic that allows CartonCloud to assign Consignments to Delivery Runs automatically.

There are two types of Zone Sets, Transport Zone Sets (used for allocating Consignments to Delivery Runs) and Income Zone Sets (used for charging). In this unit, we will focus on Transport Zone Sets; however, to better understand Transport Zone Sets, we will first talk through the differences between the two.

| **Income Zone Set** | The zones your operation uses for charging. You will use these zone when you create your Transport Rates. Income Zones allow CartonCloud to calculate your consignment charges automatically. |
| --- | --- |
| **Transport Zone Set** | The zones your operation uses for allocating consignments. These zones will work with Delivery Runs and Transport Lanes to enable CartonCloud to assign consignments to the appropriate Delivery Run automatically. |

For Coffee Warehousing and Distribution, they will need to create a Transport Zone for each geographical zone they deliver to and an Income Zone for each zone they use to base their rates off. For now, we will just focus on the Gold Coast area, but Nick will need to follow this process for all the areas the company deliver to. The map below shows how Coffee Warehousing and Distribution has divided the Gold Coast into different zones for its delivery allocation (Transport Zone Set) and rate calculation (Income Zone Set).

![](https://help.cartoncloud.com/hs-fs/hubfs/TZS%201-png.png?width=670&height=503&name=TZS%201-png.png)

Suppose Coffee Warehousing and Distribution have a consignment moving from Burleigh Heads to Paradise Point. In that case, CartonCloud will find the Income and Transport Zone associated with the suburbs of Burleigh Heads and Paradise Point.

![](https://help.cartoncloud.com/hs-fs/hubfs/TZS%202-png.png?width=670&height=503&name=TZS%202-png.png)

CartonCloud will then use the Income Zone pairing to find the associated Transport Rates and the Transport Zone pairing to find the matching Delivery Run.

**Consignment 1:**

- From address: CartonCloud, 5/27 Dover Drive, Burleigh Heads 4220
- To address: FoodWorks Paradise Point, Shop 1/3 Grice Avenue, Paradise Point 4216
- Income Zones: Area 2 → Area 1
- Transport Zones: GC Metro → GC North
- Delivery Run: Metro Daily

Follow along with Vincent as he explains further what Zone Sets are and their function in CartonCloud **(you will only need to watch the video until timestamp 1:48).**

**📹 Video:** https://www.youtube.com/embed/FVore2tk7lw?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

---

### Create a Transport Zone Set

Now that you know what a Transport Zone Set is it is time to create one in your account. You can only have one Transport Zone Set; however, within the Zone Set, you can have multiple zones.

Follow along with Vincent as he explains how to create your own Transport Zone Sets (if you watched the start of the video in the previous Unit, you can start the video from time stamp 1:49 and finish at 3:27).

**📹 Video:** https://www.youtube.com/embed/FVore2tk7lw?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

#### Need to create multiple zones?

If you know what Transport Zones you need to create, then we suggest creating your Zones in bulk using the export/import function. To do this, please see [this](https://help.cartoncloud.com/x/j4bcI) page in our Knowledge Base (see the heading Creating zones in bulk - using the export/import function).

---

### Add and assign location entries

You have now created your Transport Zones; however, CartonCloud still doesn’t know what Consignments need to be delivered to each of these Zones. As of right now, these Zones have only been named; we haven’t defined the area associated with the zone (the postcode and suburb). This unit will cover how to define your zones by creating location entries.

### What is a location entry?

A location entry is a suburb and postcode combination associated with the relevant zone and used to find a match against addresses on Consignments. For example, even though we have created a zone called ‘GC Metro’, CartonCloud still doesn’t know what Consignments need to be delivered to ‘GC Metro’. This is why you create location entries and associate the entry with the zone so that CartonCloud can associate the delivery address on the Consignment to the correct zone. For example, suppose you have a location entry for Burleigh within the GC Metro Transport Zone. In that case, CartonCloud will now know that for any Consignments with a delivery address to Burleigh, they will be going to the GC Metro zone and on the Delivery Run mapped to that zone.

### Time to create a location entry!

Follow along with Vincent from time stamp 3:27 to create your location entries.

**📹 Video:** https://www.youtube.com/embed/DvxMD0oyEhk?list=PLxs2KBNumIq6r9Wtqmbq0VvmQ2bf-Fqyl

To save time, it is suggested that you create your location entries using the export/import function. This is especially useful when you already have the locations stored in a spreadsheet format.

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Get Started with Transport Lanes](https://help.cartoncloud.com/knowledge/get-started-with-transport-lanes) 🎓

---

<a id="introduction-to-cartonclouds-tms"></a>
## Introduction to CartonCloud's TMS

_Source: https://help.cartoncloud.com/knowledge/introduction-to-cartonclouds-tms_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**This is the first article in the trail.🎓

Welcome to the TMS Basic Set up Trail! In this Trail, you will be guided through setting up your CartonCloud account for the Transport Management System (TMS) component. But before we dive into all things CartonCloud, let's take a step back and cover on a fundamental level what a transport management system (TMS) is.

### What is a Transport Management System (TMS)?

3PL Transport Management System (TMS) software is designed to help businesses plan, execute and optimise the transportation of goods. From sign-on glass with ePod’s to automated rate calculation, with a TMS, you can reduce admin time, improve customer service and increase data accuracy.

Check out the below video for a more comprehensive overview of what CartonCloud’s TMS can achieve for your business.

**📹 Video:** https://www.youtube.com/embed/jMA9uqTB37A

CartonCloud’s paperless TMS keeps your records up to date and improves operational efficiency with electronic proof of delivery, automated invoicing, driver tracking and online customer login access.

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Get Started with Organisation Settings - Transport 🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-transport)

---

<a id="introduction-to-consignments"></a>
## Introduction to Consignments

_Source: https://help.cartoncloud.com/knowledge/introduction-to-consignments_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Transport Products in CartonCloud](https://help.cartoncloud.com/knowledge/transport-products-in-cartoncloud) first.🎓

### What is a Consignment?

A Consignment in CartonCloud is a transport job. This is the job your driver is delivering on behalf of your customer.

### Consignment Types

There are a number of different types of Consignments you can create in CartonCloud. These include

- Delivery
- Pickup
- Point to Point
- Pickup + Delivery

The type of Consignments you create and how you choose to manage your Consignments will depend upon your operational requirements and setup.

For example, Nick knows that one of his customers Coastal Coffee, store most of their products at Coffee Warehousing and Distribution; however, also keep some of their stock at their own warehouse. Therefore, sometimes they will need to first pick up the freight from Coastal Coffee before bringing it back to the warehouse to sort and then later deliver. For this scenario, Nick can create a Pickup Consignment.

#### **Delivery Consignment**

**![](https://help.cartoncloud.com/hs-fs/hubfs/c1-png.png?width=1161&height=391&name=c1-png.png)**

The most common type of Consignment. Delivery Consignments only contain a delivery component. This means the driver will not be given a collection address or the option to collect a signature at the time of collection. This Consignment type is usually best for freight leaving a designated warehouse.

#### **Pickup Consignment**

**![](https://help.cartoncloud.com/hs-fs/hubfs/c2-png.png?width=553&height=250&name=c2-png.png)**

Pickup Consignments are used for collecting freight and returning it to a set warehouse. This type of Consignment will only contain a pickup component.

#### **Point to Point Consignment**

**![](https://help.cartoncloud.com/hs-fs/hubfs/c3-png.png?width=563&height=229&name=c3-png.png)**

Point-to-Point consignments contain both a Pickup and Delivery component. This allows a driver to collect a signature at both the collection and delivery points within a single Consignment.

#### **Pickup + Delivery Consignment**

This Pickup + Delivery Consignment type creates two separate consignments, one for Pickup and one for Delivery. These two consignments are linked to each other by a parent-child relationship.

### Consignment Statuses

Depending on the type of Consignment you select will dictate the statuses the Consignment will move through. The status is used to communicate at what point the Consignment is at in the process, increasing visibility and transparency.

| **Status** | **Description** |
| --- | --- |
| Awaiting Sale Order Packing | The Sale Order associated with the Consignment has not yet been packed. |
| Awaiting Pickup | The Consignment is yet to be collected by the driver. This status is only for Consignments that require a pickup. |
| In Warehouse | The Consignment is in the warehouse and is ready to go out for delivery. |
| Awaiting Pickup (Point to Point) | The Consignment is yet to be picked up by the driver. This status is only for Consignment types of Point to Point. |
| In Transit (Pickup->Warehouse) | The Consignment has been collected by the driver and is en route to the warehouse. This status is only for Consignments that require a pickup and are coming back to the warehouse. |
| In Transit (Warehouse->Delivery) | The Consignment has left the Warehouse and is with the driver en route to its delivery location. This status is for Consignments that are already at the warehouse. |
| In Transit (Pickup→Delivery) | The Consignment has been picked up and is with the driver and en route to its delivery location. This status is for Consignments that require a pickup. |
| With On Forwarder | If the Consignment is travelling with an On Forwarder and the Consignment has been handed over for delivery (left the Warehouse). |
| Delivered to Warehouse | The Consignment has now arrived at the Warehouse. This status is for pickup Consignments that do not require delivery and are coming back to the Warehouse. |
| Delivered | The Consignment has been delivered to its final destination. |
| Delivered (Point to Point) | The point to point Consignment has been delivered to its final destination and is now complete. |

### Add a Consignment

Now that you understand what a Consignment is, it is time to create one! There are many ways you can create Consignments. You can:

- Manually add a Consignment
- Your customers can manually add a Consignment through their log in
- You can use a Parser and upload multiple Consignments at once (covered in a later module)

In this unit, we will cover how to add a Consignment manually. Follow along with Vincent, as he shows you how to add a Consignment.

**📹 Video:** https://www.youtube.com/embed/tI5BRksQcu8?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Run Sheets and Allocation in CartonCloud](https://help.cartoncloud.com/knowledge/run-sheets-and-allocation-in-cartoncloud) 🎓

---

<a id="introduction-to-users-in-cartoncloud-transport-"></a>
## Introduction to Users in CartonCloud - Transport

_Source: https://help.cartoncloud.com/knowledge/introduction-to-users-in-cartoncloud-transport-_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Get Stared with Organisation Settings - Transport](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-transport)first.🎓

### What is a User in CartonCloud?

The next step in setting up your CartonCloud account is deciding who and how you want people to access your CartonCloud account.

Nick from Coffee Warehousing and Distribution manages a large team. He wants his employees to have access to CartonCloud (he doesn’t want to be doing all the work!); however, his staff have very different roles and responsibilities in the company. For example, he has two assistant managers (Carly and Rob) who manage all of the customer communications, admin and orders, several warehouse floor staff (Rose and Ned) and several drivers (Tom and Jodi). Nick also has several customers, Coastal Coffee and Country Roasters, that are excited about having visibility to their stock, access to reports and log in and add new orders.

With Users, Nick can give permission to the relevant people so they can access the Coffee Warehousing and Distribution CartonCloud account. However, Nick will also need to assign them the appropriate User Role. The User Role dictates what information and functionality the User have access to in CartonCloud. Let’s take a look at what each User role has access to.

![](https://help.cartoncloud.com/hs-fs/hubfs/users%201-png.png?width=670&height=377&name=users%201-png.png)

For Nick, he will need to assign the following roles:

- Carly and Rob (managers) = Administrator role
- Rose and Ned (warehouse staff) = Packer role
- Tom and Jodi (drivers) = Driver role
- Coastal Coffee and Country Roasters (customers) = Customer role

---

### Let's create a User!

It is now time to create your first User in CartonCloud. Follow along with Vincent, as he shows you how to add Users to your account.

**📹 Video:** https://www.youtube.com/embed/hgut_1poOfs?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

#### How to add a User

- Navigate to the Users page, Contacts > Users .

![](https://help.cartoncloud.com/hs-fs/hubfs/users%202-gif.gif?width=670&height=345&name=users%202-gif.gif)

- Click +Invite New User .

![](https://help.cartoncloud.com/hs-fs/hubfs/users%203-png.png?width=670&height=186&name=users%203-png.png)

- Enter the Name and Email (the User will use this email address to log in to CartonCloud).
- Tick Create User Now if you wish to set the password for the User now or leave the box unticked if you want the User to set up their password.

Tip: Create User Now option is helpful if you have warehouse staff or drivers who may not have an email address they can access. In this case, you can use a fake email address.

- Select the Warehouses you wish the User to have access to.
- Select the Roles you wish the User to have.
- Under Additional Settings , tick Hide all Charging information from this user if you wish for the user not to see charging information.

Tip: If you choose to hide all charging information from a user, they will not be able to see any rates against an order, Rate Card or Invoice.

- Click Continue .

Nick has several other staff members he needs to give Coffee Warehousing and Distribution CartonCloud access to. However, he doesn’t want to add each user individually (that will take up too much of his time), so he decides to create multiple users at once.

Check out our Tony Tips video, where Tony explains how to upload multiple users simultaneously!

**📹 Video:** https://www.youtube.com/embed/Zm1z94iyE4g

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Learn about Customers - Transport](https://help.cartoncloud.com/knowledge/learn-about-customers-transport) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="learn-about-customers-transport"></a>
## Learn about Customers - Transport

_Source: https://help.cartoncloud.com/knowledge/learn-about-customers-transport_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Introduction to Users in CartonCloud - Transport](https://help.cartoncloud.com/knowledge/introduction-to-users-in-cartoncloud-transport-) first.🎓

### What is a Customer?

Customers in CartonCloud are the companies you provide goods or services to. They are the companies who own the stock in your warehouse or pay you for transport services.

For example, Coffee Distribution and Warehousing has a customer called Country Roasters. Coffee Distribution and Warehousing store the coffee beans for Country Roasters in their warehouse and deliver them to their customers as new orders come in. Country Roasters pay Coffee Distribution for their services; therefore, in CartonCloud, Country Roasters will be added as a Customer.

It is important to remember that the Customer is not the individual person working at the company; instead, individuals are Users (we covered users in the previous module) who then have Customer level access. For example, for Country Roasters, one of their employees would be added as a User.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%201-png.png?width=670&height=377&name=customer%201-png.png)

You will be able to configure different settings for your Customers; for example, if you want to enforce a 2:00 pm order cut-off time for one customer and a 12:30 pm cut-off time for another, you can do so from within the Customer settings. We will cover Customer Settings in a later unit.

### What other cool things can you set up for your Customers?

- Customer-specific reports that you and your customers can access (your customers will be able to access these reports once you create them a Customer User)
- Customer Notifications that you set up from the Customer Settings. These are email notifications that are sent to your Customers upon specific event milestones in CartonCloud.
- Specific document templates used for labels, proof of deliveries and more!

---

### Add your Customers!

It's now time to add your first Customer! Follow along with Vincent, as he shows you how to add a Customer in CartonCloud.

**📹 Video:** https://www.youtube.com/embed/tohAxRBJGyw?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

### Let's add your first Customer!

Before progressing through the following steps, please ensure you have some basic information for a current customer at your organisation. We will create this customer in your account.

Please note that you can set up more complex settings and configurations in later Trails. For now, we will only create the customer with basic setting configurations.

- Navigate to the Customers page, Contacts > Customers .
- Click +Add Customer in the top left corner.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%202-png.png?width=670&height=192&name=customer%202-png.png)

- Enter the Customer's name in the Company field.
- Enter the Email and Telephone associated with the Customer. This is not a mandatory field; therefore, it can be kept blank if you wish.
- If you have multiple warehouses set up, select the warehouse you wish this Customer to have access to. If you are storing goods for your Customer over multiple warehouses, ensure you select all applicable warehouses.
- Click Add Customer .

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%203-png.png?width=318&height=290&name=customer%203-png.png)

- Click Upload Logo to add a logo against the Customer.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%204-png.png?width=564&height=241&name=customer%204-png.png)

#### Want to add more customers?

Once you have created your first customer and you feel ready to add more of your customers, you have a few options on how you can do this:

- Import customers in bulk - You can create multiple customers in bulk using the import/export feature. Note, when you use this option, the customer will be created with the default settings. See Adding Customers in Bulk for more information.
- Duplicate Customer - this allows you to create a customer easily with the same settings as the original customer. This is useful if you create your customers with similar settings and save time by having fewer customer settings to configure. See the Adding Customers and Duplicating Customers page for more information.

---

### Configure your new Customer's Settings

Now that you have created your first Customer, you can configure some of the basic settings.

- Staying on the Customer page, select your customer and then scroll down and select Edit .
- Within the Basics tab, you can add the Telephone number , and Address and update the Rate Card associated with the Customer. We will cover Rate Cards in a later page.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%205-png.png?width=670&height=312&name=customer%205-png.png)

### Customer email notifications

Next, we will run through how to set your Customer up on email notifications. Email notifications are emails delivered to your customers upon certain event triggers and milestones.

For Nick at Coffee Warehousing and Distribution, his customer Country Roasters have requested their admin staff receive emails when a new Sale Order is entered and when the order has been packed. In addition, they would also like their purchasing team to receive an email when their stock quantity reaches a certain level. Nick knows he can set all of these notifications up for the customer and does so from the Customer Settings. Follow the below steps to see how Nick can set up different notifications for different event milestones and to be sent to different email addresses for his customer.

Note: if you are following along in your account, it is recommended that you add your email address rather than your customer’s email address for the initial testing phase of using your CartonCloud account. You wouldn’t want your customer receiving an email about a test order in your account! Once you have finished all your testing, you can update the email address to be your customers!

### How to set up email notifications from the Customer Settings

- Select the Email tab.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%207-png.png?width=670&height=169&name=customer%207-png.png)

- From here, you can add a new email address and enable the relevant email notifications. Nick will need to create two separate notifications, one for the admin email and one for the purchasing team email address. For now, he will create the admin email notification for sale order import and packing.
- To add a new email address, enter the address in the New email box and click Add new email.

It is recommended you add your email address, for now, to avoid your customer receiving notifications whilst you are setting up/testing your account.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%208-png.png?width=670&height=199&name=customer%208-png.png)

- Enter a name in the Name field at the top of the page.
- Scroll down and tick the notifications you wish the email address to receive. For Nick, he will select the Sale Order notification .

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%209-png.png?width=670&height=281&name=customer%209-png.png)

- Scroll down and click Save .
- If you already have an email address against the customer, you can click Edit against the address to enable the notifications.
- You will now need to enable the notifications you selected for that email address within the Notifications tab.
- Navigate back to the Customer settings within the Email tab and click the Notifications tab. Nick will need to select ‘Send Email when Sale Order is packed’ and ‘Send Reply Always’ from the drop-down menu under ‘When to send a Sale Order Import Notification’.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%2010-png.png?width=670&height=289&name=customer%2010-png.png)

- Scroll through and select the relevant notifications you need to enable. Note that for every notification you enabled within the different email addresses, you will need to enable them from this Notifications tab.
- Scroll down and select Save .

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%2011-png.png?width=670&height=266&name=customer%2011-png.png)

*When Nick adds the purchasing team email, he will need to select ‘Stock Notification’, and then from the Notifications tab, he will need to select ‘Send Stock Warning / Expiry Notification Email (at 8:00 am AEST Mon-Fri)’.*

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Get Started with Custom Fields - Transport](https://help.cartoncloud.com/knowledge/get-started-with-custom-fields-transport) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="manifests-in-cartoncloud"></a>
## Manifests in CartonCloud

_Source: https://help.cartoncloud.com/knowledge/manifests-in-cartoncloud_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Get Started with Parsers - Transport](https://help.cartoncloud.com/knowledge/get-started-with-parsers-transport) first.🎓

### What is a Manifest?

A Manifest in CartonCloud is a grouping of Consignments for one customer on a single date that are moving together. This function was originally built for cross-docking with the idea that the Manifest can be used to check off the receipt of Consignments during a pickup.

### When to use a Manifest?

It is best to use a Manifest when you have multiple Consignments that will fit onto one truckload. It is less advantageous to use a Manifest when you have several full truckloads of Consignments.

For Nick, this is great because he has a customer who requires a number of Consignments to be collected from their warehouse, and Nick has a dedicated truck to pick up these Consignments each day. Nick will be able to instruct this Customer to send through their Consignments for pickup as a Manifest, and he will then be able to easily manage the pickup and bring the orders back to the warehouse to be sorted and sent out for delivery with other orders that were already at the warehouse.

#### Example 1 - Manifest pickup

In this example, the Customer has sent through a Manifest (via a parser) of all Consignments that need to be collected from their warehouse. Upon receiving the Manifest, CartonCloud automatically creates a Pickup Consignment ([if configured in the Customer Settings](https://help.cartoncloud.com/x/QgT8Hw)). The Manifest Pickup Consignment can then be collected and brought back to the warehouse/depot to be sorted before being dispatched for delivery to the final destination.

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%201-png.png?width=670&height=214&name=manifest%201-png.png)

#### Example 2 - Manifest pickup and deliver

In this example, the Customer has sent through a Manifest of all Consignments that need to be collected from their warehouse. The Manifest will be collected and then delivered in one movement.

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%202-png.png?width=670&height=213&name=manifest%202-png.png)

#### Example 3 - Manifest is already at the warehouse

In this example, the Customer has sent through a Manifest of all Consignments that need to go out for delivery. The Consignments are already at the warehouse and do not need to be collected (for example, they have come from a Sale Order).

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%203-png.png?width=670&height=214&name=manifest%203-png.png)

### How to create a Manifest

There are two ways you can create a Manifest, **(1) through a Parser file** or **(2) when creating a new Consignment**.

**(1) Through a Parser file**

- Once the Manifest Parser is configured to the applicable Customer, your Customer can either email the Manifest in or use the Parse a file page to upload the Manifest.
- The Manifest with all associated Consignments will now be in CartonCloud.

**Downloading the Original Manifest File**

When you import a Manifest via a Parser, you have the option to download the Manifest from the View Manifest Page. To do so:

- Navigate to the Manifest page, Transport > Manifests .
- Select the applicable Manifest.
- Select the Details tab.
- Select the blue Download button next to the Download Original Manifest File heading.

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%205-png.png?width=1600&height=505&name=manifest%205-png.png)

**(2) When creating a new Consignment**

Depending on what settings you have configured in your Organisation Settings will determine how you create a Manifest from a new Consignment.

**To configure the Manifest settings:**

- Navigate to Organisation Settings ( More > Organisation Settings ).
- Select the Transport tab.
- Within the Manifest Settings box, select if you wish to Add Consignments to Manifests by Default by selecting Yes (Default) or No.

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%206-png.png?width=1600&height=693&name=manifest%206-png.png)

- If you select Yes, the Create New Manifest will already be selected by default when creating a new Consignment. If you select No, the No Manifest option will already be selected by default.

**To create a Manifest from a new Consignment (when the setting Add Consignments to Manifests by Default is No):**

- When creating a new Consignment, fill in the applicable information and then select the drop-down arrow next to Advanced Options (at the bottom of the screen).

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%207-png.png?width=616&height=204&name=manifest%207-png.png)

- You can then choose to either Create a New Manifest or Add to Existing Manifest.

**To create a Manifest from a new Consignment (when the setting Add Consignments to Manifests by Default is Yes):**

- When creating a new Consignment, fill in the applicable information.
- At the bottom of the screen within the Manifest section, the Create a New Manifest option will already be selected by default.
- Type in the Manifest Reference.
- Alternatively, you can add the Consignment to one of the Customer's existing recent Manifests by selecting a Manifest from the displayed list under, Recent Manifests for Customer.

![](https://help.cartoncloud.com/hs-fs/hubfs/manifest%209-png.png?width=625&height=394&name=manifest%209-png.png)

---

### Using Manifests in CartonCloud

Now that you know what a Manifest is and how to create one, we can look at the Manifest arrival process. You will follow this process once the Consignments on the Manifest arrive back at your warehouse.

Follow along with Vincent as he explains the process you will need to follow once the Manifest is back at your warehouse.

**📹 Video:** https://www.youtube.com/embed/_quP2YMPHuE?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

🎉 Congratulations! You have completed the **TMS Basic Setup** CartonCloud Academy Trail.

---

<a id="run-sheets-and-allocation-in-cartoncloud"></a>
## Run Sheets and Allocation in CartonCloud

_Source: https://help.cartoncloud.com/knowledge/run-sheets-and-allocation-in-cartoncloud_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Introduction to Consignments](https://help.cartoncloud.com/knowledge/introduction-to-consignments) first.🎓

### What is a Run Sheet?

Run Sheets are used to allocate Consignments to a driver. The Run Sheet contains all the Consignments going with a single driver for that day. For example, deliveries for a single day on the Delivery Run ‘Gold Coast’ might be split up across multiple Run Sheets (East, North, West), and each Run Sheet is allocated to a different driver.

For Nick from Coffee Warehousing and Distribution, this means he will have a different Run Sheet for each of his eight drivers for each day. This will make it easier to manage workloads, organise deliveries and ensure each driver knows what they will be delivering for the day.

### How to create a Run Sheet

There are a few different ways to create Run Sheets in CartonCloud and allocate Consignments and a driver to the Run Sheet. How you conduct this process will depend upon your operational requirements and workflows. The different ways you can create a Run Sheet include:

- From the Run Sheet page
- From the Consignments page (whilst allocating Consignments and a driver to the Run Sheet in the same process)
- From the Delivery Runs page (whilst allocating Consignments and a driver to the Run Sheet in the same process)
- When using the Bulk Allocations function (covered in a later unit)

Follow along with Vincent as he talks through two ways you can create a Run Sheet whilst also allocating Consignments to the Run Sheet (from the Consignments page or the Delivery Runs page)

**📹 Video:** https://www.youtube.com/embed/QUGoGCKThdg?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

### How to use the Bulk Allocation screen

Follow along with Vincent as he explains how to use the Bulk Allocation page in CartonCloud.

**📹 Video:** https://www.youtube.com/embed/N0fzRI7Sw38?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

### Customising the Bulk Allocation screen

Nick is excited to use the Bulk Allocation screen to allocate Consignments to Run Sheets and Drivers. Nick also sees that he can customise his Bulk Allocation screen. You can configure specific controls and settings to customise the bulk allocation screen to best suit your operational needs.

Check out this page [here](https://help.cartoncloud.com/x/cgC_Hw) for more information on how to customise your Bulk Allocation screen.

### How should I allocate my Consignments?

In this module, we have covered four ways in which you can create Run Sheets and allocate Consignments to Drivers.

- From the Run Sheet page
- From the Consignments page (whilst allocating Consignments and a driver to the Run Sheet in the same process)
- From the Delivery Runs page (whilst allocating Consignments and a driver to the Run Sheet in the same process)
- When using the Bulk Allocations function (covered in a later unit)

Nick knows that he will be using a combination of methods, including the Bulk Allocation screen and from the Delivery Runs page. As you start using CartonCloud, you can test out each different allocation method and see which one works best for your operations and workflows. However, if you are still unsure, you can check out the [Which way should I allocate my Consignments](https://help.cartoncloud.com/x/-ACYHw) page in the Knowledge Base.

### Managing Run Sheets in CartonCloud

Now that you know how to create a Run Sheet, it is time to learn how you can use your Run Sheet in your day to day operations!

Nick has decided he will create his Run Sheets from within the Delivery Run and also using the Bulk Allocation screen. Once he creates the Run Sheets, he can complete tasks and access different functionality from within the Run Sheet and on the Run Sheets page. We will cover the different functionality available from within the Run Sheet and on the Run Sheets page.

#### From the Run Sheets page

Once on the Run Sheets page, **Transport**>**Run Sheets**, there are a number of different functions you can action.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%201-png.png?width=1600&height=417&name=rs%201-png.png)

#### Filters

By using the filters on the Run Sheets page, you can easily manage your Run Sheets and filter the page to only see a selection of Run Sheets that you wish to see. When you click Filter, there are several options for filtering the Run Sheets page, including Delivery Run, Driver, Date, Complete, Delivered, Exported and Vehicle.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%202-png.png?width=1600&height=366&name=rs%202-png.png)

You can also use the Today’s Complete and Today’s Incomplete tabs to manage drivers' workloads and progress.

#### Functions

Before using the different functions, you will need to use the select function on the far left to select the Run Sheets to which you wish to apply the function.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%204-gif.gif?width=1600&height=419&name=rs%204-gif.gif)

**Export**

When you click **Export**, you have multiple options of what documents you would like to export.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%205-png.png?width=1600&height=523&name=rs%205-png.png)

**Sort Run Sheets**

When you sort a Run Sheet, you are presented with a map view of the Consignments on that Run Sheet/s and can change and optimise the order of the Consignments on the Run Sheet. You can sort a single Run Sheet or select multiple Run Sheets and sort them simultaneously.

- Select the Run Sheet/s you would like to sort.
- Click Sort Run Sheets .
- Use the map to work out what Consignments you need to reorder, and using the delivery location names on the far right panel, move the titles into the order you desire.
- Click Save Consignment Order .

**Update Consignment Status**

Using the Update Consignment Status button allows you to update the status of all the Consignments on a given Run Sheet. This is useful as it will enable you to update the status of Consignments in bulk.

- Select the Run Sheet/s you wish to update.
- Click Update Consignment Status .
- Select the status you wish to update the Consignment to.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%206-png.png?width=1600&height=434&name=rs%206-png.png)

**Allocate to a Driver**

- Select the Run Sheet/s you wish to allocate a driver to.
- Click Allocate to Driver.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%207-png.png?width=1600&height=646&name=rs%207-png.png)

- Select the driver from the drop-down and click Update .

### Run Sheets List Configuration

Using the configuration button, you can choose what headings and data you want to see on the Run Sheets list view.

#### **How to customise the Run Sheets list view:**

- Select the configuration cog icon in the top right corner.

![](https://help.cartoncloud.com/hs-fs/hubfs/rs%208-png.png?width=1600&height=266&name=rs%208-png.png)

- A pop-out window will appear. From here, you can choose the data columns to be visible on the Run Sheets List view.
- To add a data column, click the tick box next to the relevant data.
- To remove the data column, un-select the tick box.
- To view completed and non-completed Run Sheets, select the ' Complete ' data column. You can also include the '#Incomplete Consignments' and '#Complete Consignments' data columns to track the number of consignments that have been delivered and the number left to be delivered.
- Select Save at the bottom of the window once all relevant data columns have been selected.

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Get Started with Parsers - Transport](https://help.cartoncloud.com/knowledge/get-started-with-parsers-transport)🎓

---

<a id="transport-products-in-cartoncloud"></a>
## Transport Products in CartonCloud

_Source: https://help.cartoncloud.com/knowledge/transport-products-in-cartoncloud_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Basic Setup Trail.**Please ensure you have read [Get Started with Income Zone Sets](https://help.cartoncloud.com/knowledge/get-started-with-income-zone-sets) first.🎓

### What is a Transport Product?

Transport Products will make your and your driver's job much easier. Rather than guessing what items are included in the transport job, you will have accurate and straightforward descriptions making it easy to know what items belong to which job and that you have delivered the correct goods.

For example, Coffee Warehousing and Distribution’s current set-up means that the driver will only see the number of items to be delivered on a job and not what these actual items are. This causes many problems as sometimes drivers will take the wrong items for a job or deliver them and then realise they are the wrong item. With CartonCloud and Transport Products, the drivers can see what these items are, avoiding mix-ups and increasing delivery accuracy. For example, a transport job may list 2 pallets and 1 carton on an order versus just listing three items on the order.

You can even add in predefined length, width and height. For example, if you deliver white goods, you could create a Transport Product called Fridge and set the predefined length, width and height against the Transport Product.

### Benefits of using Transport Products

- Reduce repetitive data entry.
- Increased efficiency when booking Consignments.
- Allows you to define rates based on the Transport Product. For example, if you are transporting a tyre from Brisbane to Sydney or a solar panel from Melbourne to Adelaide.
- Increased visibility for your drivers on what they are delivering.
- Customisation to meet your customer and operational needs.
- Increased data accuracy.

### Add Transport Products

Now that you know what a Transport Product is, it is time to create a Transport Product in your own CartonCloud account.

Follow along with Vincent, as he explains what a Transport Product is and how to add one.

**📹 Video:** https://www.youtube.com/embed/ISni6oXDVCc?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

If you have multiple Transport Products and would like to create them all at once, you can use the export/import function. See [Transport Products](https://help.cartoncloud.com/x/qwGYHw) (under the heading Export /Import Transport Products).

▶️ Follow along in the **TMS Basic Set Up Trail**...next up is [Introduction to Consignments](https://help.cartoncloud.com/knowledge/introduction-to-consignments) 🎓

---

# CartonCloud Academy > TMS Charging

<a id="charge-configurations"></a>
## Charge Configurations

_Source: https://help.cartoncloud.com/knowledge/charge-configurations_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Charging Trail.**Please ensure you have read **[Charging Methods](https://help.cartoncloud.com/knowledge/charging-methods-academy)**first.🎓

### Allow Zero Charge

Now that we have covered how to create a transport rate and the different types of charges you can create, we will now take a look at the charge configurations you can apply when you create your rates. Charge configurations are like rules which you can apply to your rates to dictate how the rate will be calculated.

The first charge configuration we will look at is, allow zero charge. By default, if a consignment charge comes out as $0 a charge error will be triggered. This default behaviour is designed to prevent consignments from being undercharged. However, by enabling ‘allow zero charge’ against a rate the charge error will not appear if the consignment charge is $0, allowing for further customisation and flexibility.

Follow along with Tony as he explains what allow zero charge is and how to enable it on your transport rates.

**📹 Video:** https://www.youtube.com/embed/ahwARQKyVJQ?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

### Maximum and Minimum Charge

The next two charge configuration we will look at is called maximum charge and minimum charge.

**Maximum charge** allows you to apply a maximum value to the transport rate to ensure the charge never exceeds a defined value. If the charge exceeds the defined value then the maximum charge will be applied. On the other hand, if the charge is less than the maximum value, then the charge calculation will remain as is.

**Minimum charge**allows you to apply a minimum value to the transport rate to ensure the charge reaches a certain defined value. If the total charges for the transport rate do not meet the minimum defined value then the minimum charge will be applied.

Follow along with Tony as he explains what Maximum Charge is and how to apply it to your transport rates.

**📹 Video:** https://www.youtube.com/embed/kECWSl7y2bk?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

#### Use cases for maximum charge

The Maximum Charge functionality ensures that a charge never exceeds an unreasonable dollar amount. This is extremely useful if you charge by a value percentage, such as the invoice value of a Consignment. Depending on the value of the product, the charge can fluctuate significantly between different Consignments, creating the need for a cap to be applied to the charge.

For example, if you have two Consignments for a customer and one has an invoice value of $50, and the other is $3000, there will be a significant charge discrepancy between the two products.

Percentage Invoice Value Charge = 20% of the Invoice Value

Consignment 1: Invoice Value = $50

Consignment 2: Invoice Value = $3000

Consignment 1 Invoice Value Charge = 50 x 0.20 = $10

Consignment 2 Invoice Value Charge = 3000 x 0.20 = $600

If a Maximum Charge of $100 is utilised for the above example:

Consignment 1 Invoice Value Charge = 50 x 0.20 = $10

Consignment 2 Invoice Value Charge = $100 (Charge is greater than $100, so the Maximum Charge is applied)

### Use Highest Charge and Charge Group

The next charge configuration we will cover is ‘Use Highest Charge’ and ‘Use Highest Charge Group’. Use highest charge allows you to dictate what charge will be applied depending on the charge that returns the highest value.

Follow along with Tony as he explains what use highest charge and charge group is and how you can apply it to your transport rates.

**📹 Video:** https://www.youtube.com/embed/ZXkQ_xed2iQ?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

Nick from Coffee Warehousing and Distribution is pleased to be using this charge configuration in his transport rates as previously his team had to manually compare which rate returned the highest charge and use that rate to charge the consignment. By using ‘Use Highest Charge’ or ‘Use Highest Charge Group’, Nick and his team won’t need to make manual calculations and will be able to build more than one charging method option into the transport rates.

### Conversions

As you have learnt throughout this module, there are a number of different charging configurations available, allowing you to create the transport rates that best suit your customers and operational needs. In addition they eliminate the need for manual calculations, saving you and your team time and increasing charging accuracy. Another charging configuration which is useful is the ability to set up conversions within your transport rates. You can set up cubic or pallet conversions and charge by the weight or by the pallet, giving you greater flexibility when creating your charges.

Follow along with Tony as he explains how to set up conversions in your transport rates and how they work.

**📹 Video:** https://www.youtube.com/embed/DM4jXZSaGzg?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

**Charge Weight:** allows you to charge per weight (adds this option to the per charge drop-down menu) and provides a cubic configuration at the top of the charge group. 10c kg - lead, pillows - add in a cubic conversion

**Charge Pallets:** allows you to charge per pallet (adds this option to the per charge drop-down menu) and provides a pallet configuration at the top of the charge group.

### Fee Category

Fee categories provide a way to create customised labels for transport rates. Once you have created a fee category you can then apply this label to the rate when you are building it. This makes it clear what the charge is for, avoiding confusion for both your team and the customer.

Follow along with Tony as he explains what a Fee Category is and how to create them in your account.

**📹 Video:** https://www.youtube.com/embed/DckQw3k1r9U?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

Fee categories are going to be very useful for Nick, as Coffee Warehousing and Distribution use a number of different charges to charge their customers consignments. Having the visibility on what each charge relates to will be beneficial to both Nick and the team and his customers.

🎉 Congratulations! You have completed the WMS Charging CartonCloud Academy Trail.

---

<a id="charging-methods-academy"></a>
## Charging Methods

_Source: https://help.cartoncloud.com/knowledge/charging-methods-academy_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Charging Trail.**Please ensure you have read [**Introduction to Transport Charging**](https://help.cartoncloud.com/knowledge/introduction-to-transport-charging) first.🎓

### Flat fee

Now that you know how to create a transport rate, it is time to take a look at the different charging methods you can use to build your transport rates. The great thing about CartonCloud’s transport rating system is that you can have multiple charges within the one rate, meaning you can use more than one charging method in the one rate. This allows for flexibility and customisation of your transport rates.

The first charging method we will cover is called flat fee. Follow along with Tony as he explains what a flat fee is and its use cases.

**📹 Video:** https://www.youtube.com/embed/P8psQPuLdSs?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

A flat fee allows you to charge a single fixed fee regardless of usage. This means that irrespective of how far or how large the delivery is, the fee will always be charged. This is useful if you have a delivery basic charge that you charge for all deliveries regardless of the type, location or size of the consignment.

### Per charge

The next transport charge method we will cover is per charge. Follow along with Tony as he explains what per charge is and how to apply it to your transport rates.

**📹 Video:** https://www.youtube.com/embed/TYLSekpJuMQ?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

Per charge charging method will charge per the set variable you select. For example, if you have a delivery fee of $10 per pallet the $10 value will be applied by the number of pallets on the consignment. You can charge per item (cubic, pallets, quantity, space, weight), invoice value, distance travelled, hours taken, or COD value.

### Conditional

The next charging method we will cover is conditional charges. Follow along with Tony as he explains what a conditional charge is and its use cases.

**📹 Video:** https://www.youtube.com/embed/BorarlVnzAk?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

Conditional charging is a more complex yet highly configurable charging method. It allows you to configure rates based upon specified conditions. For example, for a hand unload charge, you can set the charge to be applied when the word 'hand' is included in the delivery instructions.

### Sliding Scale

The next charging method we will cover is sliding scale charges. Follow along with Tony as he explains what a sliding scale charge is and its use cases.

**📹 Video:** https://www.youtube.com/embed/Oc3HS3rXMZA?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

#### Non-Cumulative and Cumulative

Follow along with Tony as he explains further how cumulative and non cumulative sliding scales work and how to apply them to your transport rates.

**📹 Video:** https://www.youtube.com/embed/9EnFVCxZszY?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

### Surcharges

The next type of charge we will cover is a surcharge. A surcharge is an additional charge on top of your transport rates. Follow along with Tony as he explains what a surcharge is and its use cases.

**📹 Video:** https://www.youtube.com/embed/KoZWAKY7dOY?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

Surcharges are created outside the Rate Card and then once created can be added to the transport rate. Surcharges are customisable and conditional, for example, a surcharge can be created which is only applied on the condition that the required delivery date is a Saturday or Sunday.

▶️ Follow along in the **TMS Charging Trail**...next up is [**Charge Configurations**](https://help.cartoncloud.com/knowledge/charge-configurations) 🎓

---

<a id="introduction-to-transport-charging"></a>
## Introduction to Transport Charging

_Source: https://help.cartoncloud.com/knowledge/introduction-to-transport-charging_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Charging Trail.**This is the first article in the Trail.🎓

Welcome to the Transport Charging Trail! In this Trail, you will be guided through how to make the most of the CartonCloud transport charging system.

Transport charges in CartonCloud are highly customisable, allowing you to configure charges to best suit your customer and operational needs. Using sophisticated charging methods and configurations, CartonCloud’s transport rating system allows you to create a seamless and automated rating process.

There are a few components that need to be set up in CartonCloud in order to be able to create transport rates. You need income zone sets and a rate card. Income zone sets are the geographical areas that you define for charging purposes. When you create your transport rates you will choose a from and to income zone to determine what consignments will use the rate you are creating. Rate cards house the rates you create and are associated with one or more customers.

CartonCloud will use the Rate Card you have created for your customer and the income zone sets (set up in the TMS Basic Set up trail) to determine what and how rates are applied to orders. The rates are automatically calculated and then added to the customer’s invoice at the end of the invoice period (or during, depending on your invoice settings).

The below diagram helps explain how CartonCloud uses Income Zone Sets, Rate Cards, and Transport Rates to automatically calculate consignment charges.

![](https://help.cartoncloud.com/hs-fs/hubfs/tc%201-png.png?width=670&height=503&name=tc%201-png.png)

Nick from Coffee Warehousing and Distribution is excited to start using CartonCloud’s transport rating system. Coffee Warehousing and Distribution previously had to calculate all their Customer’s charges manually, with their rates kept in different excel sheets and documents that sometimes were hard to keep track of. Therefore, there were sometimes rate discrepancies and customers questioning their invoices. Now that Coffee Warehousing and Distribution are using CartonCloud all the rates will be automatically calculated and applied to customers' invoices, avoiding the need for manual administrative tasks and increasing rating accuracy.

### Understanding Rate Cards

Rate Cards are fundamental to the warehouse rating system in CartonCloud. A Rate Card determines what prices your Customer will be charged for your Warehouse and/or Transport services. It also contains the settings that determine how the charges will be applied.

Every Customer in CartonCloud has a Rate Card associated with it. By default, the Rate Card associated will be the Default Rate Card; however, you will be able to change this.

Follow along with Brittany as she explains what a Rate Card is and how to create one in your CartonCloud account. Please note, this video mentions warehouse charging, however, the Rate Card set up is applicable to transport charging as well.

**📹 Video:** https://www.youtube.com/embed/E7Pi1zrFzOE?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

#### Need to create another Rate Card?

To create another Rate Card it is suggested you duplicate the first Rate Card you created to save time. Once you have duplicated the Rate Card you can make the necessary changes as required. To duplicate a Rate Card you can follow this process - [Add/Duplicate a Rate Card](https://help.cartoncloud.com/help/s/article/Add-Duplicate-a-Rate-Card)

### How to create a Transport Rate

Now that you understand what a Rate Card and Income Zone Set is we can take a deeper dive into transport rates.

Transport rates are created within the rate card. You will define a to and from income zone to determine what consignments will be utilising the rate you are creating. From here you will then be able to configure the rate, customising the charges to suit your charging requirements.

Follow along with Tony as he explains how to create a Transport Rate.

**📹 Video:** https://www.youtube.com/embed/hZsJgS66IP0?list=PLxs2KBNumIq4QofgErhrHScd9iuUGrLDq

Nick from Coffee Warehousing and Distribution now understands the basic principles of creating a transport rate. He is looking forward to the next module where he will learn how each charging method works and he can decide how he would like to set up his transport rates.

▶️ Follow along in the **TMS Charging Trail**...next up is [**Charging Methods**](https://help.cartoncloud.com/knowledge/charging-methods-academy) 🎓

---

# CartonCloud Academy > TMS Mobile App

<a id="delivering-a-consignment-and-recording-an-electronic-pod"></a>
## Delivering a Consignment and recording an electronic POD

_Source: https://help.cartoncloud.com/knowledge/delivering-a-consignment-and-recording-an-electronic-pod_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Mobile App Trail.**Please ensure you have read [**Learn about transport app features**](https://help.cartoncloud.com/knowledge/learn-about-transport-app-features) first.🎓

An essential feature of the transport mobile app is the ability to record electronic PODs (ePODs). An electronic POD is not much different from a paper POD; however, you can record the recipient’s signature on the mobile app, record what was delivered/wasn’t delivered, and all the information will be saved against the record. The POD can then be accessed via the CartonCloud web app and emailed to the customer. With this process, there is a limited chance of the POD being lost as all information is available electronically vs being on paper.

Coffee Warehousing and Distribution are currently using paper to record their PODs. Once the driver brings the paper POD back to the office, the admin staff must scan the document and email it to the customer. However, there have been numerous cases where the paper POD gets misplaced and never makes it back to the customer causing customer frustration and loss of important data. With CartonCloud and the mobile app, Coffee Warehousing and Distribution can electronically record the POD and make it available for the customer instantly (it can even be emailed to them directly) and eliminate manual and time-consuming tasks for their staff.

#### Benefits of using electronic PODs:

- Streamlines delivery process
- Maintains data integrity
- Reduced risk of data loss
- Reduction in manual and repetitive admin tasks
- Customers can access information instantly
- Information can be processed more efficiently

#### How to record a POD using the CartonCloud mobile app

Using the transport CartonCloud mobile app you can record an electronic POD upon delivering a Consignment. This POD will then be made available against the Consignment in the web app, accessible for the customer and admin users. You also can set up a customer notification so that once the Consignment has been marked as delivered, they will be notified of the delivery and receive the POD instantly.

Follow along with Tony as he steps through how to record a POD when delivering a Consignment on the CartonCloud mobile app.

**📹 Video:** https://www.youtube.com/embed/tMfWf2QKD_c?list=PLxs2KBNumIq4KQMFfJ1GN9f2cC_gQ908F

### What happens once the Consignment has been marked as delivered?

Once the Consignment has been marked as delivered, it will no longer appear on the mobile app. The status on the web app will be updated to ‘Delivered’, and the POD will be available for admin users and the customer. If you have the correct customer notifications set up. In that case, the customer and the Consignment recipient will receive an email once the Consignment has been delivered with a copy of the electronic POD. See [Customer Notifications](https://help.cartoncloud.com/x/uAC-I) for more information.

Nick is excited to start using the mobile app to record electronic PODs. He is excited about the benefits it will bring to both his customers and the drivers.

▶️ Follow along in the **TMS Mobile App Trail**...next up is [**Lodging a Consignment error**](https://help.cartoncloud.com/knowledge/lodging-a-consignment-error) 🎓

---

<a id="introducing-the-transport-mobile-app"></a>
## Introducing the transport mobile app

_Source: https://help.cartoncloud.com/knowledge/introducing-the-transport-mobile-app_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Mobile App Trail.**This is the first article in the Trail.🎓

Welcome to the TMS Mobile App Trail! In this Trail, you will learn about the CartonCloud transport mobile application and how to use it in your operations. CartonCloud’s mobile application is purposely designed to complement and work with the web application to support the agile and on-the-go work of warehousing and transport. In this Trail, we will focus on the transport features, and the warehouse features will be covered in the WMS Mobile App Trail.

Nick is the Manager at Coffee Distribution and Warehousing. Coffee Distribution and Warehousing store and deliver coffee beans for several different customers. Nick is in charge of setting up CartonCloud for the company. He has completed the set-up of the web application for transport and warehouse. He is excited to learn how to use the mobile application to enhance his warehouse and transport processes further!

CartonCloud’s transport mobile app enhances reliability and efficiency in the delivery process. In addition, the Transport app provides increased visibility for the customer, driver and your operation staff. The key features and benefits of the mobile warehouse application are listed below.

#### Transport mobile app features

- Delivering Consignments and recording an electronic POD
- Capturing signature upon delivery
- Recording and lodging errors
- Recording adhoc charges
- Scan allocate
- Cash on delivery
- Editing consignments
- Consignment error notifications (for admin staff)
- ETA text messages
- Driver tracking

#### Transport mobile app benefits

- Improved delivery efficiency
- Increased visibility and traceability of deliveries
- Ability to record information on the go
- Improved data accuracy
- Real-time data and information for customers
- Reduced manual and admin tasks
- Reduction in paperwork and lower risk of information being lost

### Downloading the mobile application

The first step in using the mobile application is downloading it onto your device! You can download the CartonCloud app onto either your iOS or Android device. The application can be downloaded from the [Apple App Store (for iOS)](https://itunes.apple.com/au/app/cartoncloud/id977857739?mt=8) or the [Google Play Store (for Android)](https://play.google.com/store/apps/details?id=com.cartoncloud.transport&hl=en).

Once you have downloaded the CartonCloud application and opened it on your device, you will be prompted to log in. Use the same login credentials you use for the CartonCloud web application.

You will need to ensure you have the [user role](https://help.cartoncloud.com/x/PAOYHw) Driver [enabled against your user](https://help.cartoncloud.com/x/LgOYHw)to access the mobile app with your login.

Follow along with the below video for steps on how to login into the CartonCloud mobile app.

**📹 Video:** https://www.youtube.com/embed/NVFBfgLEiW4

### Pair it with a scanner!

If you use an iPhone or Android phone, pair it with a [Bluetooth barcode scanner](https://help.cartoncloud.com/x/iAK-I) to enable barcode scanning when using the Cartoncloud app. If you want a mobile computer (which has an inbuilt scanner), you can check out [this](https://help.cartoncloud.com/x/iAK-I) page for recommended devices.

Once you have logged into the mobile app, select a [User Mode](https://help.cartoncloud.com/x/CwmYHw). Each User Mode offers different functionality and accommodates a different warehouse or transport process. For transport, you will only need to use one User Mode, Delivering.

### Navigating the mobile app

Once you have logged into the mobile app, select a [User Mode](https://help.cartoncloud.com/x/CwmYHw). Each User Mode offers different functionality and accommodates a different warehouse or transport process. For transport, you will only need to use one User Mode, Delivering.

To access the User Modes selection page, use the hamburger menu icon. From here, you can select Switch Mode.

You can also access the CartonCloud mobile app Settings and Notifications or refresh your current page.

### Settings

From the [Settings](https://help.cartoncloud.com/x/BQmYHw) page, you can:

| ABOUT | See what version of the application you are currently operating. We are consistently updating the application for performance improvements and new features, so ensure you [always operate the latest version of the app](https://help.cartoncloud.com/x/M4LWIQ)! |
| --- | --- |
| ORGANISATION | The CartonCloud tenancy you are in (tenancy is your CartonCloud account). |
| WAREHOUSE | The Warehouse you are in. If you have multiple warehouses, you will have a drop-down arrow to select the relevant warehouse you wish to be in. You will need to ensure the user has access to the warehouse to see the warehouse in the drop-down menu. |
| USER SETTINGS | [Enable Push Notifications](https://help.cartoncloud.com/x/LwqYHw) Show Consignment Origin/Show Additional Pickup / Delivery Info (transport only) [Enable Rapid Sale Order Packing](https://help.cartoncloud.com/x/sAuYHw) |
| DEFAULT MAP FOR NAVIGATION | Transport only |
| SUPPORT | [Send Diagnostics](https://help.cartoncloud.com/x/uwiYHw) |

Now that Nick understands how to set up the mobile application, he uses the checklist below to ensure he has everything ready to start using the warehouse app.

### Checklist before using the mobile app

- Do you have devices to use the application on? (this could be as simple as an iPhone or Android mobile device or something more robust such as a mobile computer. See this page for recommended devices)
- If using a mobile device, do you have bluetooth barcode scanner to connect the phone to? (See this page for more information)
- Have you downloaded the application onto your device from either the Apple App Store or Google Play Store?
- Have you added a Packer User Role to the relevant Users in CartonCloud?
- Do the relevant Users have access to the warehouse they are working in?

▶️ Follow along in the **TMS Mobile App Trail**...next up is **[Learn about transport app features](https://help.cartoncloud.com/knowledge/learn-about-transport-app-features)**🎓

---

<a id="learn-about-transport-app-features"></a>
## Learn about transport app features

_Source: https://help.cartoncloud.com/knowledge/learn-about-transport-app-features_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Mobile App Trail.**Please ensure you have read [**Introducing the transport mobile app**](https://help.cartoncloud.com/knowledge/introducing-the-transport-mobile-app) first.🎓

It’s time to jump into some of the more exciting features of the mobile transport app. Nick from Coffee Warehousing & Distribution is excited to make his driver's job easier and to provide greater visibility to his customers.

Follow along with Tony as he speaks through the key features of the transport app.

**📹 Video:** https://www.youtube.com/embed/YZmyq9gweFs?list=PLxs2KBNumIq4KQMFfJ1GN9f2cC_gQ908F

### Leave a comment against the Consignment or address

With the CartonCloud transport mobile app, you have the ability to add comments to the Consignment or address for other users to see (excluding customers). This allows for increased visibility and communication between users, especially drivers and admin staff. For example, if the driver had to wait longer before being able to unload the delivery, the driver can leave a comment against the Consignment, so admin staff know to charge for waiting time. Or, if the delivery site has particular delivery requirements, they can record this against the address at the time of making the delivery so that for future deliveries to that site, other drivers will know.

**How to add a comment to the Consignment**

- Select the relevant Consignment
- Click the comment icon against the Consignment.

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%201-png.png?width=329&height=713&name=tms%201-png.png)

- Enter the comment.
- Click Post .

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%202-jpg.jpeg?width=291&height=582&name=tms%202-jpg.jpeg)

- This comment will now appear against the Consignment on the web and mobile app for all users (excluding customers).

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%203-png.png?width=302&height=624&name=tms%203-png.png)

### How to add a comment to the address

- Open the Consignment.
- Click the comments button against the address.

![](https://help.cartoncloud.com/hs-fs/hubfs/comment%20address-png.png?width=286&height=592&name=comment%20address-png.png)

- Type in the comment

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%204-png.png?width=306&height=663&name=tms%204-png.png)

- Click Post .

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%205-png.png?width=297&height=643&name=tms%205-png.png)

- The comment will now appear against the address in the mobile and web app for all users.

**Beneifts of using comments:**

- Easily communicate between the driver and admin users. Comments that are made by either the driver or admin user will show on the mobile app and web app for both users.
- Record important information against the Consignment.
- Useful for drivers as they can then record important delivery information for future deliveries.

### Call or text the ETA

The CartonCloud mobile apps allow drivers to contact customers by call or text message (assuming a telephone number has been provided for the customer's address via the web app). One of the contact options is an ETA text message. While the standard text message option will have an empty body, an ETA text message is pre-filled with various information about the consignment as well as an estimated arrival time.

**How to call or text the ETA to the delivery address contact:**

Please note this is only possible if you have loaded the phone number against the delivery address in the web app. Please see here for more information.

- Select the phone icon next to the Delivery Details.

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%206-jpg.jpeg?width=281&height=567&name=tms%206-jpg.jpeg)

- Click Text ETA or if you would rather send a unique message (not use the ETA template) click Text or if you would prefer to call click Call.

![](https://help.cartoncloud.com/hs-fs/hubfs/tms%207-jpg.jpeg?width=259&height=521&name=tms%207-jpg.jpeg)

- A new text message window will appear. Click the arrow send icon.

For more information on ETA text messages click [here](https://help.cartoncloud.com/x/0gmYHw)

### Customs fields on the mobile app

CartonCloud allows you to create custom fields to record specific data against different records within CartonCloud. These custom fields can be made visible on the mobile app. For example, if you choose to create a custom field for the opening hours of a delivery address, you could choose to have this displayed on the mobile app, making it easier for drivers to know when to make the delivery by.

For information on how to set these custom fields up please click [here](https://help.cartoncloud.com/x/sw03I).

### Edit Consignment Items

Drivers on the mobile app have the ability to edit Consignment Items on a Consignment. In addition, you can choose to trigger a Consignment Error on the web app when the Driver makes a change to the Consignment. This way, you are aware of the change, which allows you to proactively manage communications with the customer and action any relevant admin activities related to the change.

For information on how to edit Consignment Items and the related configuration set ups please click [here](https://help.cartoncloud.com/x/WgdwIg).

Nick now knows the major features of the transport mobile app and can already see the benefits it is going to bring Coffee Warehousing and Distribution and their drivers and customers.

### Map view on the mobile app

Another great feature of the transport mobile app is the map view. Map view within the CartonCloud mobile apps is a powerful tool to not only provide the location and type/status of consignments in one easy glance but also to optimise a driver's route. Nick is interested in learning more about this tool to see if it is something that his drivers will be able to use.

Follow along with Tony as he demonstrates how to use the map view on the mobile app.

**📹 Video:** https://www.youtube.com/embed/ZzPgcgzhAGE?list=PLxs2KBNumIq4KQMFfJ1GN9f2cC_gQ908F

▶️ Follow along in the **TMS Mobile App Trail**...next up is [**Delivering a Consignment and recording an electronic POD**](https://help.cartoncloud.com/knowledge/delivering-a-consignment-and-recording-an-electronic-pod) 🎓

---

<a id="lodging-a-consignment-error"></a>
## Lodging a Consignment error

_Source: https://help.cartoncloud.com/knowledge/lodging-a-consignment-error_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Mobile App Trail.**Please ensure you have read [**Delivering a Consignment and recording an electronic POD**](https://help.cartoncloud.com/knowledge/delivering-a-consignment-and-recording-an-electronic-pod) first.🎓

This module will cover how to lodge an error on the mobile app during transit and upon delivering a Consignment. As we all know, sometimes things don’t go as planned when transporting and delivering goods. For example, sometimes the freight is damaged in transit, poor weather conditions mean the carton has water damage or the way the truck has been packed means upon unloading the truck, you notice a carton has a tear.

With CartonCloud, you can record the damages at the time of noticing them and/or at the time of delivery. This will create a Consignment error which flags the Consignment with the admin staff, allowing them to take the necessary actions.

That may be contacting the customer or adjusting the Consignment rates. CartonCloud allows for the seamless recording of and communication of important information that may arise during the transport process in the form of Consignment Errors.

### What is a Consignment error?

Consignment Errors are reported by Users of CartonCloud and can be reported from within the Consignments themselves. They range from Undeliverable to having their Cartons/Pallets count changed. Consignment Errors are visible only to Admins and Onforwarders.

When Consignment Errors are reported, they will need to be actioned by a CartonCloud user within your organisation with Administration level permission.

### Reasons to lodge a Consignment error

- Damaged freight
- Missing items in a Consignment
- Receiver rejecting an order
- Delivery address issues (closed or incorrect address)
- Temperature rejection
- System error

### Benefits of Consignment errors with CartonCloud

- Reduced risk of the information/error being lost (not having to rely on memory or writing it on paper)
- Recording the information at the time for data accuracy and timeliness
- Transparency (between drivers and admin staff)
- Data integrity
- Customer communication (able to communicate more effectively and timely with customers)

### How to record a Consignment error on the CartonCloud mobile app

There are two ways in which you can record a Consignment error on the mobile app:

- At any point in the Consignment’s journey (before leaving the warehouse, in transit etc.)
- When recording the POD

Each method will be covered in the following two units.

### How to resolve a Consignment error

Once a Consignment error has been lodged against a Consignment, admin staff can choose to notify the customer or close the error. Please click [here](https://help.cartoncloud.com/x/oQGYHw) for more information on how to do this.

Nick knows his drivers will use the Consignment error function when on the road and delivering Consignments. His admin staff are also pleased as this means they will be across what is happening on the road and are able to communicate this with the customer.

### Lodging an error whilst delivering a Consignment

Now that you know what a Consignment error is and the benefits of lodging them on the mobile app let us cover how to create one when delivering a Consignment. As covered in the previous unit, one of the ways you can lodge a Consignment error on the mobile app is when delivering a Consignment and recording the POD. Follow along with Tony as he delivers a Consignment and records an error.

**📹 Video:** https://www.youtube.com/embed/osjAzm82m94?list=PLxs2KBNumIq4KQMFfJ1GN9f2cC_gQ908F

### Lodging a Consignment Error when in transit

Now that you know how to lodge a Consignment error when recording a POD, it is time to cover how to lodge an error when the Consignment is in transit. Follow along with Tony as he steps through recording a Consignment error whilst in transit.

**📹 Video:** https://www.youtube.com/embed/osjAzm82m94?list=PLxs2KBNumIq4KQMFfJ1GN9f2cC_gQ908F

▶️ Follow along in the **TMS Mobile App Trail**...next up is [**Scan Allocation**](https://help.cartoncloud.com/knowledge/scan-allocation-academy)🎓

---

<a id="scan-allocation-academy"></a>
## Scan Allocation

_Source: https://help.cartoncloud.com/knowledge/scan-allocation-academy_

🔔 Note: this article is part of the **CartonCloud Academy - TMS Mobile App Trail.**Please ensure you have read [Lodging a Consignment error](https://help.cartoncloud.com/knowledge/lodging-a-consignment-error) first.🎓

### How to use Scan Allocation

Follow along in the below video as we demonstrate how to use the scan allocation function on the mobile app.

**📹 Video:** https://www.youtube.com/embed/HA4ctUZTSqw

🎉 Congratulations! You have completed the TMS Mobile App CartonCloud Academy Trail.

---

# CartonCloud Academy > WMS Basic Setup

<a id="cartoncloud-inbound-process-explained"></a>
## CartonCloud Inbound Process Explained

_Source: https://help.cartoncloud.com/knowledge/cartoncloud-inbound-process-explained_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Get started with Parsers - Warehouse](https://help.cartoncloud.com/knowledge/get-started-with-parsers-warehouse) first🎓

### Inbound Process with CartonCloud

CartonCloud’s inbound process is managed through the utilisation of Purchase Orders. Purchase Orders are inbound orders that allow you to receive stock into your warehouse.

Purchase Orders make the inbound process seamless and efficient. You will be able to record vital information against the order and the stock (such as batch numbers, SSCC etc.), ensure all charges relating to the order are captured and easily track stock. This makes  stock and inventory management easier for you and your customers.

Once a Purchase Order is created (by yourself, your customer or integration with another software), you will be able to approve the order. Once approved and the order is at your warehouse, you can receive it, verify it, and allocate it to a warehouse location. Once allocated to a warehouse location, the Purchase Order will start accumulating storage charges and is then available to be assigned to an outgoing order (Sale Order). To better understand this process, you can refer to the below diagram. You will see the different statuses a Purchase Order moves through and what actions are completed at each stage.

### Some great things you will love about Purchase Orders!

Throughout this process, you can set up specific notifications to be sent to your customers. For example, a notification can be sent to your customer once the order has been received and once it has been verified.

You can also record adhoc charges against the Purchase Order throughout the process. For example, the number of containers that had to be unloaded or the number of pallets wrapped. Don’t worry; your predetermined inbound rates and storage charges will also be automatically calculated; however, the adhoc charges are for charges that require input quantity and that vary for each order. This means you don’t miss any charges and can invoice your customers for all movements or add-ons that may arise through the process (charging will be covered in greater detail in another Trail).

Nick is super excited to use Purchase Orders in his warehouse inbound process! Nick believes by using Purchase Orders, the process will be streamlined, data accuracy will improve, and his customers will be provided with more up-to-date information automatically.

---

### Creating a Purchase Order

Now that you know what a Purchase Order is, it is time to add one!

There are many different ways a Purchase Order can come into CartonCloud.

![](https://help.cartoncloud.com/hs-fs/hubfs/PO%201-png.png?width=385&height=402&name=PO%201-png.png)

In this unit, we will focus on how to add a Purchase Order manually. Your customers can follow this same process using their CartonCloud login.

Follow along with Vincent as he steps through the process of adding a Purchase Order.

**📹 Video:** https://www.youtube.com/embed/jGDELzGil7M?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

Nick wants to make his processes as automated as possible and already knows he will be encouraging his customers to use Parsers to email their orders through so that they are automatically created in CartonCloud.

### Receiving a Purchase Order

Now that you have created a Purchase Order, it is time to learn how to receive it into your warehouse.

Follow along with Vincent as he steps through how to receive a Purchase Order on the web app.

Note that warehouse staff can complete the below process on the mobile app.

**📹 Video:** https://www.youtube.com/embed/jnbUG-avg7E?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

---

### Photos and Documents on Purchase Orders

With Photos and Documents on Purchase Orders, users can attach photos, videos, and documents directly to Purchase Orders through both the mobile and web app. These attachments—whether photos, videos, or documents—are linked to the Purchase Order.

Check out the diagram below for a visual breakdown of how Purchase Orders, Documents, and Attachments are connected.

![](https://help.cartoncloud.com/hs-fs/hubfs/PO%202-png.png?width=670&height=377&name=PO%202-png.png)

#### Key Points

- A Document has attachments and attachments can be videos, photos or other documents (ie: PDF).
- Documents have two different visibility options:
  - Internal only : no customer access. Admins and packers can edit.
  - Shared with customer: customer can view. Admins and packers can edit.
- Documents are split into two tiers, Essentials (available in all WMS plans), and Advanced (available through Warehouse Premium).
- Capture and upload photos at receipt on the mobile or from your device’s photo library.
- Users can add and edit Documents on the web app but only add (not edit) on the mobile app.
- On the Purchase Order Allocated and Verified email if there are Documents associated with the Purchase Order and they are Customer level visibility, a link to the Document will be included in the email. See Customer Settings - Email (Notifications) for more information.

#### Available Workflows

- **Documents on the Mobile app** - add Documents upon receiving stock in the warehouse.
- **Documents on the Web app** - add Documents to the Purchase Order at any stage in the order process (any status) from the web app.

#### Use Cases / Benefits

- Enables warehouse workers to provide photo (and video) evidence of received goods.
- Allows issues such as damages to be easily communicated and shared with customers.
- Provides greater transparency and visibility to customers.
- Provides greater transparency internally with photo visibility supplied at the time of receipt or damage and document history for who uploaded the attachment.
- Enables an advanced inbound process.
- Enables greater compliance and regulation standards for your customers.
- Increased service offering and value to your customers.

#### How to record Photos and Documents on Purchase Orders via the Web App

Documents can be created on Purchase Orders at any stage though the order process. The Purchase Order can be in any status for a Document to be created.

Follow along with Vincent as he shows you how to upload Photos and Documents to Purchase Orders via the web app.

**📹 Video:** https://www.youtube.com/embed/tKTgbhXq3HQ

▶️ Follow along in the WMS Basic Set Up Trail...next up is [CartonCloud Outbound Process Explained](https://help.cartoncloud.com/knowledge/cartoncloud-outbound-process-explained) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="cartoncloud-outbound-process-explained"></a>
## CartonCloud Outbound Process Explained

_Source: https://help.cartoncloud.com/knowledge/cartoncloud-outbound-process-explained_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [CartonCloud Inbound Process Explained](https://help.cartoncloud.com/knowledge/cartoncloud-inbound-process-explained) first.🎓

### Outbound Process with CartonCloud

CartonCloud’s outbound process is managed through Sale Orders. A Sale Order is the outbound order leaving your warehouse.

CartonCloud ensures accuracy and efficiency throughout the outbound process by utilising automatic rating, customisation, settings to enhance picking accuracy and seamless integrations with eCommerce platforms and shipping/dispatch software.

You or your customer will place the order through EDI, API, web upload, or a Parser. Once the order is approved (if it was added manually), it will be available for your warehouse staff to pick. Once the Sale Order has been picked and packed by your warehouse staff, it will then be dispatched from your warehouse. Depending on your operation workflow, the order may be picked up by a third-party transport company, or alternatively, you may manage the transport component and will deliver the goods yourself (stay tuned for the next unit where we will cover using CartonCloud WMS and TMS together for this exact use case!).

To better understand this process, you can refer to the below diagram. You will see the different statuses a Sale Order moves through and what actions are completed at each stage.

![](https://help.cartoncloud.com/hs-fs/hubfs/SO%201-png.png?width=670&height=252&name=SO%201-png.png)

Some great things you will love about Sale Orders!

Using the CartonCloud mobile app, you can force your pickers to scan to confirm the warehouse location, product and custom fields (for example, Batch Numbers), ensuring the correct products are picked from the correct location matching the order specifications.

In addition, all picking and outbound charges are captured and automatically added to your customer’s invoice. You can even record adhoc charges against the order, such as labelling or wrapping fees.

You can set up Integrations with your customer’s eCommerce platform, such as Shopify, so that new Sale Orders are automatically sent through to CartonCloud, without you or your customer having to do a thing!

---

### Creating a Sale Order

Now that you know what a Sale Order is, it is time to add one!

There are many different ways a Sale Order can come into CartonCloud.

![](https://help.cartoncloud.com/hs-fs/hubfs/SO%202-png.png?width=354&height=370&name=SO%202-png.png)

Follow along with Vincent as he steps through the process of adding a Sale Order.

**📹 Video:** https://www.youtube.com/embed/6lfJtP7SBfY?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

---

### Learn about Sale Order Settings

Nick has specific operational workflows that must be followed and customers with varying requirements that must be met. To ensure these processes are followed, and his customer’s needs are met, Nick can use the settings in CartonCloud to enforce these processes and requirements. There are many different settings in CartonCloud; however, in this unit, we will focus on Sale Order Settings (located in the Customer Settings). Sale Order Settings are specific to each Customer, meaning each customer’s Sale Order Settings can be configured differently. This enables you to alter your processes or requirements for each customer, making it easier for you and keeping your customers happy!

Follow along with Vincent as he talks through some of the key Sale Order Settings.

**📹 Video:** https://www.youtube.com/embed/UnkO3_aP7NM?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

---

### How to Pack a Sale Order

Now that you have created a Sale Order and you understand the different settings associated with Sale Orders it is time to pack the order!

Follow along with Vincent as he steps through how to pack a Sale Order on the web app.

**📹 Video:** https://www.youtube.com/embed/1V9zwFRcxCI?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

▶️ Follow along in the WMS Basic Set Up Trail...next up is [Setting up CartonCloud for WMS & TMS](https://help.cartoncloud.com/knowledge/setting-up-cartoncloud-for-wms-tms) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="get-started-with-organisation-settings-warehouse"></a>
## Get started with Organisation Settings - Warehouse

_Source: https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Introduction to WMS](https://help.cartoncloud.com/knowledge/introduction-to-wms) first.🎓

### What are Organisation Settings?

The first step in your CartonCloud journey begins with setting up your Organisation Settings! Organisation Settings is like the control centre of your CartonCloud account; it allows you to customise and manage how you utilise CartonCloud within your operations.

There are a number of different settings within CartonCloud, which is great because it means you can easily adapt CartonCloud to meet your operational and customer needs. However, this means it is important that you understand the different types of settings and where to find them. We will cover settings throughout later pages; however, for now, let's focus on Organisation Settings.

**Organisation Settings** relate to your whole organisation. This means changes to Organisation Settings will apply to all your Customers and aspects of your CartonCloud account. The only way to override these settings is to make changes at the Customer Settings. Customer Settings will only apply to that applicable customer.

For example, Nick is the Manager at Coffee Distribution and Warehousing. Coffee Distribution and Warehousing store and deliver coffee beans for a number of different customers with varying operational needs. Nick is in charge of setting up CartonCloud for the company. He wants to know what type of settings he can set up in the Organisation Settings and the ones he needs to set up in the Customer Settings. He refers to the below table to better understand the difference.

| Organisation Settings | Customer Settings |
| --- | --- |
| Settings applied will apply to the entire organisation | Settings applied will only apply to that particular customer |
| You can override Organisation Settings using Customer Settings | You can not override Customer Settings; what you apply at the Customer level will override what you set up at the Organisation level |
| Your basic organisation information needs to be set up here (including logo) | Only customer-specific information will be set up here (customer address, phone number, etc) |
| Some settings in Organisation Settings can only be set up at the Organisation level | Some settings in Customer Settings can only be set up at the Customer level |

With Organisation and Customer Settings your options for meeting customer and operational needs are endless. We will cover Customer Settings in more detail in a later page. For now, we will focus on Organisation Settings.

We will be covering the following topics:

- Navigating the Organisation Settings
- First step...your Organisation's name
- Add your company branding
- Add your Organisation's address
- Set up your Warehouse

### Navigating the Organisation Settings

Let’s navigate to the Organisation Settings in your account.

- You can either select More > Organisation Settings or type Organisation Settings into the Search for anything! Box.
- You can move between each setting by utilising the tab headings at the top of the page.

Now, let’s start setting up your Organisation Settings! We will continue to use Nick from Coffee Warehousing and Distribution as our example. This is his first day setting up CartonCloud, so where should he start? To begin, Nick needs to update his company logo, name and address.

Follow along with Vincent, as he shows you how to set up your company logo, name and address from the Organisation Settings ***(only watch up to timestamp 4:00)***.

**📹 Video:** https://www.youtube.com/embed/PnWGiCcjSH4

### First step...your Organisation's name!

It’s time to add your organisation's name to CartonCloud. Let’s start by navigating to your Organisation Settings:

- Click the More tab in the top right corner.
- Select Organisation Settings .
- Click the Organisation tab.
- Enter your Organisation name in the Nickname field.
- You can also enter your Website , phone number and default currency .

![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Nov-19-2025-02-51-48-6819-AM.png?width=670&height=319&name=image-png-Nov-19-2025-02-51-48-6819-AM.png)

### Add your company branding!

Next, let’s add your company logo! From within the Organisation Settings:

- In the far right panel under Logo , click Upload Logo .

**![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Nov-19-2025-02-52-04-5229-AM.png?width=670&height=319&name=image-png-Nov-19-2025-02-52-04-5229-AM.png)**

- Select Choose File . Select your logo.
- Click, Upload Logo

### Add your Organisation's address

Now, it is time to add your Organisation’s address to CartonCloud, from within the Organisation Settings:

- Click the Address tab.
- Click Add New Address .

![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Nov-19-2025-02-53-35-0570-AM.png?width=670&height=325&name=image-png-Nov-19-2025-02-53-35-0570-AM.png)

- Search for your organisation in the Company name field. If it does not appear, fill in the address manually in the other address fields.
- Scroll down and click Add Address .
- Click Add New Address String . For more information on Address Strings click here .
- Enter your Organisation's name in the Address String name field.
- Select your Organisation's address from the Allocated to address drop down field.
- Click Add Address String . For more information on Address Strings, please click here .
- Enter the Default Latitude and Longitude (which will be shown in maps) if you wish.
- Scroll down and click Save .

Will you be using international addresses or are your operations based outside of Australia?

If you are using addresses outside of Australia or your operations are based outside of Australia, you will need to enable the **Allow International Addresses to be entered in CartonCloud**setting.

Nick knows that some of his customer's ship to New Zealand, so he will need to turn this setting on.

To turn this setting on (within the Organisation Settings):

- Select the Features & Options tab.
- Under Address Configuration , tick Allow International Addresses to be entered in CartonCloud
- Select your Default Country Address from the drop-down.
- Scroll down to the bottom of the page and select Save .

---

### Set up your Warehouse

Now that you have your basic Organisation Settings configured, you can set up your Warehouse. If you are only using the Transport Management System and don’t have a warehouse as such, you can think of this as your depot.

Nick knows Coffee Warehousing and Distribution have a warehouse in Sydney and also Melbourne. He will update the existing warehouse with the Sydney details and add another warehouse for the Melbourne warehouse.

Follow along with Vincent, as he sets up the Warehouse (watch from time stamp 4:00).

**📹 Video:** https://www.youtube.com/embed/PnWGiCcjSH4

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Learn about Customers.](https://help.cartoncloud.com/knowledge/learn-about-customers)[🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="get-started-with-parsers-warehouse"></a>
## Get started with Parsers - Warehouse

_Source: https://help.cartoncloud.com/knowledge/get-started-with-parsers-warehouse_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Products Explained](https://help.cartoncloud.com/knowledge/products-explained) first.🎓

CartonCloud enables automated workflows and operational efficiencies, reducing admin and repetitive manual tasks, giving you and your team time back in your day for the important tasks. One way in which CartonCloud does this is through the use of Parsers.

### What are Parsers?

Parsers are able to read data and then import the data into CartonCloud in a format the system can understand. Using the data, the Parser can create or update a record in CartonCloud, for example, a Sale Order or Consignment.

Parsers are usually in the format of an excel spreadsheet (xlsx, csv etc.), and the document will contain all the data pertaining to the orders. There are three ways in which Parsers can be uploaded to CartonCloud:

1. Web application upload - from the ‘Parse a file’ page on the web app, the parser file can be uploaded directly to CartonCloud. The customers can also use the ‘Parse a file’ page from their customer login.
2. Email - the parser file can be uploaded via emailing the file to a set email address. Once emailed in, the orders will be automatically created in CartonCloud.
3. File Transfer Protocol (FTP) - for this method, please contact the CartonCloud team for more information.

### Benefits of using Parsers

- Eliminates repetitive data entry
- Reduces time spent creating/sending through orders for both your staff and your customers
- Data integrity - as the data only has to be entered once (as you can copy and paste the data into the file or use the file the data is already formatted in), you reduce the chances of error
- Reduce correspondence and admin time spent with the customer as they can email the order straight into CartonCloud, eliminating your involvement in the process

### Use cases for using Parsers

- If your customer has a large number of orders which need to be entered.
- If the data for the orders already exist in the format (for example, the software that generates the orders exports them in a CSV format)

### Types of Parsers

There are a number of different Parsers you can use with your CartonCloud account. This is great news for Nick from Coffee Warehousing and Distribution because he wants all his customers to send their orders in through email Parsers. This includes their Sale Orders and Purchase Orders.

One of Nick’s customers, Country Roasters, has invoices that need to be attached to each of their Sale Orders. Country Roasters doesn’t want to have to manually upload each invoice to the corresponding Sale Order in CartonCloud. Nick looks through the list of available Parsers and sees the Sale Order Invoice Parser. With this Parser, Country Roasters will be able to send through the invoice documents via email and they will automatically be uploaded and attached to the relevant Sale Order in CartonCloud. This works by scanning the uploaded document for the reference number and matching it against the Sale Order it is to be attached to.

Please see the list of available Parsers [here](https://help.cartoncloud.com/help/s/article/List-of-Parsers).

---

### How to set your Customer up with Parsers

Now that you know what a Parser is and the benefits they bring to you and your Customer’s operations it is time to learn how to set your Customer’s up with Parsers.

Nick knows that Country Roasters will be using Parsers to send through their Purchase Orders and Sale Orders. Country Roasters have requested that they email the file in. Nick knows this is possible with CartonCloud, so he downloads the default Purchase Order and Sale Order parser template to send them. He also mentions to them that if they require other fields to be parsed in or would like a custom template, the CartonCloud team can set this up at a cost.

Before Nick sends the template to Country Roasters, he needs to configure the particular Parsers to the customer. Follow along with Vincent as he steps through the process of configuring a Parser to the Customer.

**📹 Video:** https://www.youtube.com/embed/pZyNrDOD7yk?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

---

### Parsers in action

Now that you know what a Parser is and how to set them up for your Customers it is time to cover how to use the Parsers!

### Ways to upload a Parser

As covered in the first unit, there are three ways Parsers can be uploaded to CartonCloud.

1. Web application upload - from the ‘Parse a file’ page on the web app, the parser file can be uploaded directly to CartonCloud. The customers can also use the ‘Parse a file’ page from their customer login.
2. Email - the parser file can be uploaded via emailing the file to a set email address. Once emailed in, the orders will be automatically created in CartonCloud.
3. File Transfer Protocol (FTP ) - Please contact the CartonCloud team for more information on this method.

We will cover web upload and email in this unit. For information on File Transfer Protocol (FTP), please [contact the CartonCloud team](https://support.cartoncloud.com/servicedesk/customer/portal/2/user/login?destination=portal%2F2).

This is great for Nick as he can offer his customers options on how they wish to send through their orders, making the order creation process flexible and adaptable to best meet their operational workflows.

Parsers are not only limited to customers. Nick and his team will also be able to use Parsers and both upload methods if required. This is helpful if a customer cannot upload their orders or there were mistakes with the original orders, and the orders need to be deleted and uploaded again.

### Web upload (‘Parse a file’)

You can upload Parsers through the web app using the ‘Parse a file’ page in CartonCloud. This page is accessible for both Administrator and Customer user roles.

You will need to ensure you have followed the steps in the ‘How to set your Customer up with Parsers’ unit for your customers to be able to upload Parsers through the web application. If you have not completed this step, please go back to this unit or see [this](https://help.cartoncloud.com/x/GAK_Hw) page for steps to set up your customer with the Parser.

**Steps to upload a Parser using the ‘Parse a file’ page**

You will need to ensure you have downloaded the template associated with the Parsers and use this template to fill in your order data. Once you have filled in the template, you will upload this file to CartonCloud.

**(1) Download the template**

- Navigate to the relevant Parser by typing Parsers into the Search for anything bar. Click View against the relevant Parser.
- Click Download .
- Alternatively, you can use this page to download the relevant file.

**(2) Parse the file**

- Navigate to the Parse a file page, More > Parse a file .
- Select the Customer you wish to parse the file for.
- Select the relevant Parser.
- Select the file.
- Select if you wish to send an import email to the customer.
- Click Upload .

### Emailing in Parsers

The second option is to email the file into CartonCloud. This is an efficient and effective workflow for your customers as they can upload their orders in one simple step! They won’t even need to be logged in to CartonCloud.

To do this, you will need to ensure you have followed the steps in the ‘How to set your Customer up with Parsers’ unit for your customers to be able to email Parsers through to CartonCloud. If you have not completed this step, please go back to this unit or see [this](https://help.cartoncloud.com/x/GAK_Hw) page for steps to set up your customer with the Parser.

Follow along with Vincent as he shows you how to email a Parser into CartonCloud. Watch the video from timestamp 5:43.

**📹 Video:** https://www.youtube.com/embed/pZyNrDOD7yk?list=PLxs2KBNumIq6PLaOCBAtxFW1-A8KxNnFe

▶️ Follow along in the WMS Basic Set Up Trail...next up is [CartonCloud Inbound Process Explained](https://help.cartoncloud.com/knowledge/cartoncloud-inbound-process-explained) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="introduction-to-products-unit-of-measure"></a>
## Introduction to Products Unit of Measure

_Source: https://help.cartoncloud.com/knowledge/introduction-to-products-unit-of-measure_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Purchase Order Product Custom Fields Explained](https://help.cartoncloud.com/knowledge/purchase-order-product-custom-fields-explained) first.🎓

### What is a Product Unit of Measure in CartonCloud?

All products in CartonCloud are measured in a particular unit of measure. Each product contains a Base Unit Of Measure, which is the smallest sellable quantity of the product. CartonCloud uses the Base Unit of Measure to convert the quantity into other units of measure using the conversions set up against the product.

For Nick from Coffee Warehousing and Distribution, this is excellent news! His customer, Country Rosters, sells their products at the individual bottle level or in bulk by carton or pallet. Nick will now be able to set up the different units of measure for each of his customer’s products and set up conversions to make it easier for his staff and customers.

![](https://help.cartoncloud.com/hs-fs/hubfs/product%20unit%20of%20measure%201-png.png?width=670&height=408&name=product%20unit%20of%20measure%201-png.png)

### Benefits of using Product Unit of Measure

- Product unit of measure conversions will be utilised during sale order optimisation to prevent breaking larger quantities where possible. For example, if six bottles make up a carton and you have a location that contains three bottles and another with six bottles, CartonCloud will prioritise taking from the three bottles as this cannot be sold as a Carton.
- Handling charges for both Sale Orders and Purchase Orders will be Scaled automatically. So, picking six bottles from a location will automatically charge handling for one carton rather than six bottles.
- Pick Lists will be shown in Scaled Quantities (so rather than saying to pick 60 Bottles, it'll say one pallet).
- Stock Reports can be shown in Scaled Quantities (very useful when dealing with Pallet Conversions).

---

Now that you understand what a Products Unit of Measure is and how they are used in CartonCloud, it is time to learn how to add a Products Unit of Measure in CartonCloud.

### How to create a Products Unit of Measure

Follow along with Vincent as he explains how to add a Product Unit of Measure.

**📹 Video:** https://www.youtube.com/embed/8HrEj3UVF5k?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

Nick from Coffee Warehousing and Distribution is ready to set up his Products Unit of Measure and conversions for Country Roasters. Nick will need to:

- Navigate to the Products page, Warehouse > Products.
- Click Related and then Products Unit of Measure or in the Search for anything type Product Unit of Measure .

Note, once you are at the Products Unit of Measure page, you will notice that there is already some Products Unit of Measure set up in your account. However, these are locked and can not be deleted. Therefore, if you see the Product Unit of Measure you want to create, we strongly advise you don’t create a new one but rather use the one already created.

Nick can see that Carton and Pallet have already been created as a Product Unit of Measure in his account (created by default in every account), so he will only need to create a Bottle Product Unit of Measure.

- Select +Add Product Unit of Measure .
- Enter the **Name** for the Product Unit of Measure and the **Code**.
- Select the **Category** (Mass, Volume, Count).
- Enable the **Oversize Warnings** if you wish to be notified of when you may be over-allocating to a warehouse location. See [Oversize Warnings](https://help.cartoncloud.com/display/KB2/Products+Units+of+Measure#ProductsUnitsofMeasure-oversize) for more information.
- If you wish to link the Product Unit of Measure to a Transport Product/Consignment, see [Mapping Product Unit of Measures to Consignment Fields/Transport Products](https://help.cartoncloud.com/help/s/article/Mapping-Product-Unit-of-Measures-to-Consignment-Fields-Transport-Products) for more information.
- Click **Save**.

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Learn about Warehouse Locations](https://help.cartoncloud.com/knowledge/learn-about-warehouse-locations) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="introduction-to-users-in-cartoncloud-warehouse"></a>
## Introduction to Users in CartonCloud - Warehouse

_Source: https://help.cartoncloud.com/knowledge/introduction-to-users-in-cartoncloud-warehouse_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Learn about Customers - Warehouse](https://help.cartoncloud.com/knowledge/learn-about-customers) first. 🎓

### What is a User in CartonCloud?

The next step in setting up your CartonCloud account is deciding who and how you want people to access your CartonCloud account.

Nick from Coffee Warehousing and Distribution manages a large team. He wants his employees to have access to CartonCloud (he doesn’t want to be doing all the work!); however, his staff have very different roles and responsibilities in the company. For example, he has two assistant managers (Carly and Rob) who manage all of the customer communications, admin and orders, several warehouse floor staff (Rose and Ned) and several drivers (Tom and Jodi). Nick also has several customers, Coastal Coffee and Country Roasters, that are excited about having visibility to their stock, access to reports and log in and add new orders.

With Users, Nick can give permission to the relevant people so they can access the Coffee Warehousing and Distribution CartonCloud account. However, Nick will also need to assign them the appropriate User Role. The User Role dictates what information and functionality the User have access to in CartonCloud. Let’s take a look at what each User role has access to.

![](https://help.cartoncloud.com/hs-fs/hubfs/users%201-png.png?width=670&height=377&name=users%201-png.png)

For Nick, he will need to assign the following roles:

- Carly and Rob (managers) = Administrator role
- Rose and Ned (warehouse staff) = Packer role
- Tom and Jodi (drivers) = Driver role
- Coastal Coffee and Country Roasters (customers) = Customer role

---

### Let's create a User!

It is now time to create your first User in CartonCloud. Follow along with Vincent, as he shows you how to add Users to your account.

**📹 Video:** https://www.youtube.com/embed/My5kF3TVAWY

#### How to add a User

- Navigate to the Users page, Contacts > Users .

![](https://help.cartoncloud.com/hs-fs/hubfs/users%202-gif.gif?width=670&height=345&name=users%202-gif.gif)

- Click +Invite New User .

![](https://help.cartoncloud.com/hs-fs/hubfs/users%203-png.png?width=670&height=186&name=users%203-png.png)

- Enter the Name and Email (the User will use this email address to log in to CartonCloud).
- Tick Create User Now if you wish to set the password for the User now or leave the box unticked if you want the User to set up their password.

Tip: Create User Now option is helpful if you have warehouse staff or drivers who may not have an email address they can access. In this case, you can use a fake email address.

- Select the Warehouses you wish the User to have access to.
- Select the Roles you wish the User to have.
- Under Additional Settings , tick Hide all Charging information from this user if you wish for the user not to see charging information.

Tip: If you choose to hide all charging information from a user, they will not be able to see any rates against an order, Rate Card or Invoice.

- Click Continue .

Nick has several other staff members he needs to give Coffee Warehousing and Distribution CartonCloud access to. However, he doesn’t want to add each user individually (that will take up too much of his time), so he decides to create multiple users at once.

Check out our Tony Tips video, where Tony explains how to upload multiple users simultaneously!

**📹 Video:** https://www.youtube.com/embed/Zm1z94iyE4g

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Purchase Order Product Custom Fields Explained](https://help.cartoncloud.com/knowledge/purchase-order-product-custom-fields-explained)  [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="introduction-to-wms"></a>
## Introduction to WMS

_Source: https://help.cartoncloud.com/knowledge/introduction-to-wms_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**This is the first article in the trail.**🎓**

### What is a Warehouse Management System (WMS)?

Welcome to the WMS Basic Set up Trail! In this Trail, you will be guided through setting up your CartonCloud account for the warehouse management system (WMS) component. But before we dive into all things CartonCloud, let's take a step back and cover on a fundamental level what a warehouse management system (WMS) is.

3PL warehouse management system (WMS) software is designed to digitise and automate warehouse management, saving you and your business time and money! From simplifying order creation to storage optimisation, a WMS provides automated workflows to streamline your operations.

Check out the below video for a more comprehensive overview of what CartonCloud’s WMS can achieve for your business.

**📹 Video:** https://www.youtube.com/embed/mwaMfBX6AzQ

CartonCloud’s robust and feature-filled WMS is simple in design with ease of use and customisation at the forefront. Customisation allows you to adapt the system to best meet your operations, business and customer needs.

Follow along with Vincent, as he introduces you to the WMS and some of its core concepts.

**📹 Video:** https://www.youtube.com/embed/Esbh9mACjew

▶️ Follow along in the WMS Basic Set Up Trail...next up is [Get started with Organisation Settings 🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="learn-about-customers"></a>
## Learn about Customers - Warehouse

_Source: https://help.cartoncloud.com/knowledge/learn-about-customers_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Get started with Organisation Settings - Warehouse](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)first.🎓

### What is a Customer?

Customers in CartonCloud are the companies you provide goods or services to. They are the companies who own the stock in your warehouse or pay you for transport services.

For example, Coffee Distribution and Warehousing has a customer called Country Roasters. Coffee Distribution and Warehousing store the coffee beans for Country Roasters in their warehouse and deliver them to their customers as new orders come in. Country Roasters pay Coffee Distribution for their services; therefore, in CartonCloud, Country Roasters will be added as a Customer.

It is important to remember that the Customer is not the individual person working at the company; instead, individuals are Users (we covered users in the previous module) who then have Customer level access. For example, for Country Roasters, one of their employees would be added as a User.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%201-png.png?width=670&height=377&name=customer%201-png.png)

You will be able to configure different settings for your Customers; for example, if you want to enforce a 2:00 pm order cut-off time for one customer and a 12:30 pm cut-off time for another, you can do so from within the Customer settings. We will cover Customer Settings in a later unit.

### What other cool things can you set up for your Customers?

- Customer-specific reports that you and your customers can access (your customers will be able to access these reports once you create them a Customer User)
- Customer Notifications that you set up from the Customer Settings. These are email notifications that are sent to your Customers upon specific event milestones in CartonCloud.
- Specific document templates used for labels, proof of deliveries and more!

---

### Add your Customers!

It's now time to add your first Customer! Follow along with Vincent, as he shows you how to add a Customer in CartonCloud.

**📹 Video:** https://www.youtube.com/embed/0HnAfynt3BA

### Let's add your first Customer!

Before progressing through the following steps, please ensure you have some basic information for a current customer at your organisation. We will create this customer in your account.

Please note that you can set up more complex settings and configurations in later Trails. For now, we will only create the customer with basic setting configurations.

- Navigate to the Customers page, Contacts > Customers .
- Click +Add Customer in the top left corner.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%202-png.png?width=670&height=192&name=customer%202-png.png)

- Enter the Customer's name in the Company field.
- Enter the Email and Telephone associated with the Customer. This is not a mandatory field; therefore, it can be kept blank if you wish.
- If you have multiple warehouses set up, select the warehouse you wish this Customer to have access to. If you are storing goods for your Customer over multiple warehouses, ensure you select all applicable warehouses.
- Click Add Customer .

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%203-png.png?width=318&height=290&name=customer%203-png.png)

- Click Upload Logo to add a logo against the Customer.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%204-png.png?width=564&height=241&name=customer%204-png.png)

#### Want to add more customers?

Once you have created your first customer and you feel ready to add more of your customers, you have a few options on how you can do this:

- Import customers in bulk - You can create multiple customers in bulk using the import/export feature. Note, when you use this option, the customer will be created with the default settings. See Adding Customers in Bulk for more information.
- Duplicate Customer - this allows you to create a customer easily with the same settings as the original customer. This is useful if you create your customers with similar settings and save time by having fewer customer settings to configure. See the Adding Customers and Duplicating Customers page for more information.

---

### Configure your new Customer's Settings

Now that you have created your first Customer, you can configure some of the basic settings.

- Staying on the Customer page, select your customer and then scroll down and select Edit .
- Within the Basics tab, you can add the Telephone number , and Address and update the Rate Card associated with the Customer. We will cover Rate Cards in a later page.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%205-png.png?width=670&height=312&name=customer%205-png.png)

### Customer email notifications

Next, we will run through how to set your Customer up on email notifications. Email notifications are emails delivered to your customers upon certain event triggers and milestones.

For Nick at Coffee Warehousing and Distribution, his customer Country Roasters have requested their admin staff receive emails when a new Sale Order is entered and when the order has been packed. In addition, they would also like their purchasing team to receive an email when their stock quantity reaches a certain level. Nick knows he can set all of these notifications up for the customer and does so from the Customer Settings. Follow the below steps to see how Nick can set up different notifications for different event milestones and to be sent to different email addresses for his customer.

Note: if you are following along in your account, it is recommended that you add your email address rather than your customer’s email address for the initial testing phase of using your CartonCloud account. You wouldn’t want your customer receiving an email about a test order in your account! Once you have finished all your testing, you can update the email address to be your customers!

### How to set up email notifications from the Customer Settings

- Select the Email tab.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%207-png.png?width=670&height=169&name=customer%207-png.png)

- From here, you can add a new email address and enable the relevant email notifications. Nick will need to create two separate notifications, one for the admin email and one for the purchasing team email address. For now, he will create the admin email notification for sale order import and packing.
- To add a new email address, enter the address in the New email box and click Add new email.

It is recommended you add your email address, for now, to avoid your customer receiving notifications whilst you are setting up/testing your account.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%208-png.png?width=670&height=199&name=customer%208-png.png)

- Enter a name in the Name field at the top of the page.
- Scroll down and tick the notifications you wish the email address to receive. For Nick, he will select the Sale Order notification .

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%209-png.png?width=670&height=281&name=customer%209-png.png)

- Scroll down and click Save .
- If you already have an email address against the customer, you can click Edit against the address to enable the notifications.
- You will now need to enable the notifications you selected for that email address within the Notifications tab.
- Navigate back to the Customer settings within the Email tab and click the Notifications tab. Nick will need to select ‘Send Email when Sale Order is packed’ and ‘Send Reply Always’ from the drop-down menu under ‘When to send a Sale Order Import Notification’.

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%2010-png.png?width=670&height=289&name=customer%2010-png.png)

- Scroll through and select the relevant notifications you need to enable. Note that for every notification you enabled within the different email addresses, you will need to enable them from this Notifications tab.
- Scroll down and select Save .

![](https://help.cartoncloud.com/hs-fs/hubfs/customer%2011-png.png?width=670&height=266&name=customer%2011-png.png)

*When Nick adds the purchasing team email, he will need to select ‘Stock Notification’, and then from the Notifications tab, he will need to select ‘Send Stock Warning / Expiry Notification Email (at 8:00 am AEST Mon-Fri)’.*

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Introduction to Users in CartonCloud - Warehouse](https://help.cartoncloud.com/knowledge/introduction-to-users-in-cartoncloud-warehouse) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="learn-about-warehouse-locations"></a>
## Learn about Warehouse Locations

_Source: https://help.cartoncloud.com/knowledge/learn-about-warehouse-locations_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Introduction to Products Unit of Measure](https://help.cartoncloud.com/knowledge/introduction-to-products-unit-of-measure) first.🎓

### What is a Warehouse Location in CartonCloud

Warehouse Locations in CartonCloud are designed to replicate the locations you have set up in your physical warehouse. You can then allocate stock to these locations in CartonCloud to reflect what is physically in the location in your warehouse. Stock will only be charged storage once it is allocated to a Warehouse Location.

### How to name your Warehouse Locations in CartonCloud

You have complete control over how you name your Warehouse Locations in CartonCloud. You could use free text and choose to call a location ‘Bulk Location’ or ‘Receiving Bay’, or you can use the recommended naming conventions and have the location names automatically populate. The great thing is that you can use both options and have some locations using the recommended naming conventions and some locations with free text names! Let’s quickly run through how the recommended naming conventions work.

Nick from Coffee Warehousing and Distribution has a map of his warehouse; we will use that to explain how the naming conventions work. CartonCloud breaks down the locations by row, bay and level. As you can see on the birds-eye view map of Nick’s warehouse, he has rows and bays.

![](https://help.cartoncloud.com/hs-fs/hubfs/WL%201-png.png?width=670&height=517&name=WL%201-png.png)

Nick has row AA through to row FF. In each row, he has bay 01 to bay 06. If we looked at a warehouse location side on, we would see the different levels the locations have.

![](https://help.cartoncloud.com/hs-fs/hubfs/WL%202-png.png?width=572&height=225&name=WL%202-png.png)

CartonCloud will join the row, bay and level to create a Warehouse Location name. For example, the warehouse location in row AA, bay 01 on level 3 would look like AA-01-03.

This naming convention is simple and allows you to create warehouse locations in bulk more easily. We will cover more on this in the following unit!

#### How to add a single Warehouse Location

There are many different ways you can add Warehouse Locations in CartonCloud. You can add them in bulk via import/export or create them individually. We are going to start by adding a single Warehouse Location.

Follow along with Vincent as he steps through how to create a single warehouse location.

**📹 Video:** https://www.youtube.com/embed/rV7oK_rHwpQ?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

After looking at his warehouse map, Nick thinks he has a pretty good idea of what Warehouse Locations he needs to create. However, he will first add a single warehouse location to ensure he understands how Warehouse Locations are created.

If you are following along in your account, we suggest making sure you know exactly what Warehouse Locations you need to create for your warehouse, as you can not delete Warehouse Locations.

---

### Adding Warehouse Locations in Bulk

Now that you understand how to create a warehouse location manually, we can look at adding Warehouse Locations in bulk. This is a great way to add your Warehouse Locations if you are following the naming system we covered in the first unit.

Follow along with Vincent as he steps through how to add Warehouse Locations in bulk in your CartonCloud account.

**📹 Video:** https://www.youtube.com/embed/TsLcXWD-I74?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

Nick from Coffee Warehousing and Distribution will use the suggested naming convention for his Warehouse Locations. So adding Warehouse Locations in bulk will work well for Nick. Using Nick’s warehouse map, he will start by adding row AA.

It is important to know what row you will be adding in bulk and the number of bays and levels in the row before you add your Warehouse Locations in bulk.

---

### Creating Warehouse Locations via import/export

Another way you can create Warehouse Locations is via import/export. This process includes exporting your Warehouse Locations in an XLS format, updating them or adding new ones to the file and then importing them back into CartonCloud to create new locations or update existing ones. This allows you to create multiple Warehouse Locations simultaneously, across multiple rows, regardless of whether you use the suggested naming convention. If you are not using the CartonCloud naming convention, then it is suggested that you use this method to create your Warehouse Locations.

Follow along with Vincent as he shows you how to create new Warehouse Locations via the import/export function.

**📹 Video:** https://www.youtube.com/embed/98s4QoiCvBo?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

Nick has created one row of his Warehouse Locations, AA, using the Add Warehouse Locations in Bulk process. However, he already has a list of his locations in an excel file, so he will use that data to create his new Warehouse Locations.

If the import is unsuccessful due to an issue such as formatting, an error banner will be displayed, and the error will be described.

If you receive an error, you can find out why it occurred by following the same actions as the animation below.

![](https://help.cartoncloud.com/hs-fs/hubfs/WL%204-gif.gif?width=670&height=409&name=WL%204-gif.gif)

---

### What are Warehouse Location barcodes?

For every Warehouse Location in CartonCloud, you can set up a barcode for that location. With a barcode set up for the location and printed on a location label, you can scan the barcode for actions such as moving, picking and putaway (on the mobile app). This helps to make your picking and putaway process as efficient and accurate as possible! It also allows you to maximise the benefits of the CartonCloud mobile app and the [Scan Move](https://help.cartoncloud.com/x/dAyYHw) feature.

Nick from Coffee Warehousing and Distribution plans for his team to use the CartonCloud mobile app for both the inbound and outbound process. Nick doesn’t have any existing Warehouse Location labels, so he will need to start from scratch and create them with CartonCloud. However, if Nick already had labels and barcodes set up, he could simply add the existing barcodes to the warehouse locations in CartonCloud.

### Creating Warehouse Location barcodes

Nick can’t remember if he created barcodes during the Warehouse Location creation process. So, he is going to check if he has barcodes set up by exporting his Warehouse Locations.

- Navigate to the Warehouse Locations page, Warehouse > Warehouse Locations.
- Select More > Export to XLS.
- Open the file.

Nick notices that the barcode column is blank; he will need to load barcodes against the Warehouse Locations.

- In the name column, select the cell in the first row of warehouse locations. Hold down CTRL + SHIFT + down arrow . This will highlight the whole column down from the first cell you selected.
- Copy the data.
- Paste the data in the barcode column .

![](https://help.cartoncloud.com/hs-fs/hubfs/WL%205-gif.gif?width=670&height=385&name=WL%205-gif.gif)

- Save the file.
- Navigate back to the Warehouse Locations page. Select More>Import XLS .
- Select the file and click Upload File .
- Once the file has been imported, the Updated tab will show the changes made to the Warehouse Locations. Select Confirm Import .

### Already have Warehouse Location barcodes in your warehouse?

If you already have warehouse location barcodes in your warehouse, you can follow the same process as above; however, instead of copying the name column, simply copy your existing barcodes into the barcode column.

### Printing Warehouse Location labels

Now that your barcodes are set up, it is time to print your Warehouse Location labels. The label will include the barcode to enable barcode scanning during the putaway and picking process.

CartonCloud’s Warehouse Location labels print on A4 pages. This is great because it allows you to easily load your printer with PPS label paper to print your labels in bulk.

You can follow the instructions [here](https://help.cartoncloud.com/x/wwaYHw) on how to print your labels from within CartonCloud. However, if you have a large number of Warehouse Locations to print, we suggest following [this](https://help.cartoncloud.com/x/SpbcI) process using the Avery templates.

Nick has printed his labels and has his team placing them on the warehouse locations in the warehouse so they are ready for when they start using CartonCloud!

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Products Explained](https://help.cartoncloud.com/knowledge/products-explained) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="products-explained"></a>
## Products Explained

_Source: https://help.cartoncloud.com/knowledge/products-explained_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Learn about Warehouse Locations](https://help.cartoncloud.com/knowledge/learn-about-warehouse-locations) first.🎓

### What are Products?

Products in CartonCloud are not the stock itself but rather the SKU or Product Master. In other words, a Product is a template that stores information, characteristics and rules associated with a particular item in your warehouse.

For example, Nick has received a list of products from his customer Country Roasters. Nick will need to add these products into CartonCloud so that when his customer sends through new orders, the information about the product is already there in CartonCloud.

![](https://help.cartoncloud.com/hs-fs/hubfs/products%201-png-3.png?width=670&height=362&name=products%201-png-3.png)

Products are customer-specific. Each of your Customers will have a number of Products that only apply to them.

### Product Settings

Products are highly customisable, meaning you can configure them to meet your customer’s requirements, operational needs, and workflows. How you set up your Product impacts the stock allocation and charging logic.

Product Settings can be configured when adding a Product and, once created, can be edited at any time.

For example, Nick’s customer, Country Roasters, has requested that the stock with the first expiry date is added to orders first. The customer has also requested that they be notified when the stock reaches a certain threshold. All of these requirements can be set up in the Product Settings.

### Product Types

Nick’s customer has also flagged some Products on the list as needing to be kept chilled or frozen. Nick can select the appropriate Product Type from the Product Settings to match the temperature requirements. For example, he will give the Product Ice Coffee, a Product Type of Chilled.

### Product Statuses

Product Statuses are similar to Product Types in that they help communicate more information about the Product; however, the Product's status can change depending on the conditions of the product and uncontrollable variables in the order lifecycle. For example, if a Product is damaged during transit, you can update the state of the stock to ‘Damaged’.

Every product will have a default status; however, the status of the stock can then be updated at any point during the inbound and outbound process.

You can also choose which Product Statuses don’t count towards storage charges. For example, if stock is missing and you update the status to ‘Missing’, you won’t want to charge storage as you don’t have it!

There are some Product Statuses already loaded into CartonCloud, such as ‘Damaged by Carrier’ and ‘Quarantine’; you can choose to use these statuses or create your own. Follow the instructions on [this](https://help.cartoncloud.com/x/HwO_Hw) page to create your own Product Statuses.

Now that Nick understands what a Product is, he is ready to start adding the Products into CartonCloud for his customer, Country Roasters.

---

### How to create a Product

Now that you know what a Product is in CartonCloud, it is time to create a Product in your account!

Nick is going to choose the product ‘House Blend Beans’ from the list of products his customer gave him as the first Product to create.

If you are following along in your account, we suggest you create a product for the customer you already set up in your account.

Nick needs to follow the instructions specified on the product list given to him by his customer. To meet the requirements specified on the list, he will need to make sure he:

- Sets up the correct Product Unit of Measure conversions (as specified on the list)
- He will need to choose FEFO (first expiry first out) as the stock selection method as the customer has requested the stock with the first expiry be selected first.
- He will need to select ‘Enable low stock notification’ and enter 100 bags as the low stock threshold. This means the customer will be notified once the product reaches 100 bags.
- Select Ambient as the Product Type.
- The batch number, production facility and expiry date fields will need to all be set up from the Customer Settings as Purchase Order Product Custom Fields and Product Custom Fields, as covered in previous units. For more information, see Setting up Custom Fields for Purchase Order Product Custom Fields .

Follow along with Vincent as he steps through how to create a Product in CartonCloud.

**📹 Video:** https://www.youtube.com/embed/U0Ul0roLX4o?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

Note that you will have to select a Stock Selection Method for the Product you are creating. The Stock Selection Method determines how CartonCloud will choose which stock will go out on an order. Please see [this](https://help.cartoncloud.com/x/wwG_Hw) article for more information.

### How to create Products via export/import

Now that Nick has created one Product for his customer, Country Roasters, he is ready to create the rest. When creating multiple Products, you should use the export/import function to do so.

### What is the export/import function?

The export/import function allows you to export your current Products in an excel document format, edit the existing products or add new ones to the document, and then import them back into CartonCloud. When you import the document back into CartonCloud, any updates or new Products on the document will be updated in CartonCloud. This is a great way to create Products when your customer has sent through a long Product list, and the Products have similar settings (which means you can copy and paste a lot of the data!).

### How to create Products via export/import

Follow along with Vincent as he shows you how to create new Products via export/import.

**📹 Video:** https://www.youtube.com/embed/14cE5U8lk7A?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

Since Nick has his list of Products from his customer, this process will be even easier! All Nick needs to do is export his list of Products from CartonCloud, add the new Products to the document and import them back into CartonCloud. Once he has imported the file, the new Products will be created in CartonCloud.

Tip: if you only wish to create new Products for one Customer at a time and copy the settings you already have for their existing Products, then it is suggested you filter the page before exporting. Using the filter option of Customer, select the relevant Customer and then click Export Products.

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Get started with Parsers - Warehouse](https://help.cartoncloud.com/knowledge/get-started-with-parsers-warehouse) [🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="purchase-order-product-custom-fields-explained"></a>
## Purchase Order Product Custom Fields Explained

_Source: https://help.cartoncloud.com/knowledge/purchase-order-product-custom-fields-explained_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [Introduction to Users in CartonCloud - Warehouse](https://help.cartoncloud.com/knowledge/introduction-to-users-in-cartoncloud-warehouse) first🎓

### What is a Purchase Order Product Custom Field

The great thing about CartonCloud is that it is super customisable for all your operational and customer needs. One way CartonCloud offers customisation is through custom fields. Custom fields allow you to select what information you wish to be recorded against certain items in CartonCloud. For example, you can have custom fields against addresses, Sale Orders, Customers and Products (just to name a few!).

For Nick from Coffee Warehousing and Distribution, this is great news because his customer, Country Roaster, has already provided him with a long list of certain information that needs to be recorded, and they have visibility on it.

We will be focusing on Purchase Order Product Custom Fields in this unit; however, to better understand how Purchase Order Product Custom Fields work, we will compare the difference between **Product Custom Fields** and **Purchase Order Product Custom Fields**.

Nick’s customer Country Roasters has requested:

1. That the production date and batch number be recorded against each product line of stock on a Purchase Order.
2. That the roasting facility for each product is visible against the product (they roast their beans at two different facilities, and certain products are roasted at each).
3. That the Container Number is recorded against each order (the orders come to Nick’s warehouse via containers)

Nick knows that it is possible to record custom data against entities in CartonCloud; however, he isn’t sure what type of custom fields he needs to set up. He uses the below definitions to help him better understand where he needs to be recoding this information for his customer:

- Purchase Order Product Custom Field : allows you to record information directly against a line of stock on a Purchase Order. For example, Batch Number, SSCC, Pallet ID, or Production Date. Purchase Order Product Custom Fields are customer specific.
- Product Custom Fields : record information against the product record. It is usually used to record extra information related to that particular product. For example, shoe size could be a product custom field.
- Purchase Order Custom Fields: record information against the entire Purchase Order. For example, a container number or carrier information.

Using these definitions, Nick now knows what custom fields he needs to set up. Nick goes ahead and sets up the following custom fields:

1. A **Purchase Order Product Custom Field**for **Batch Number** and **Production Date**. This will be recorded against the individual line of stock.

![](https://help.cartoncloud.com/hs-fs/hubfs/POP%201-png.png?width=670&height=113&name=POP%201-png.png)

2. A **Product Custom Field** for **Roasting Facility**.

![](https://help.cartoncloud.com/hs-fs/hubfs/POP%202-png.png?width=670&height=340&name=POP%202-png.png)

3. A **Purchase Order Custom Field** for **Container Number**. This data is recorded against each individual Purchase Order.

![](https://help.cartoncloud.com/hs-fs/hubfs/POP%203-png.png?width=670&height=328&name=POP%203-png.png)

---

Now that you know what a Purchase Order Product Custom Field is, we can start to create these fields in your CartonCloud account.

### How to set up Purchase Order Product Custom Fields for your Customer

Purchase Order Product Custom Fields are customer specific, meaning you can have different custom fields for each customer or the same ones. You can have up to 10 different Purchase Order Product Custom Fields for each customer.

Follow along with Vincent, as he explains how to set up Purchase Order Product Custom Fields.

**📹 Video:** https://www.youtube.com/embed/BvbQPmqqbd8

Let’s see how Nick would go about setting up his Purchase Order Product Custom Fields for his customer, Country Roasters.

- Navigate to the Customers Page, Contacts > Customers .
- Select the relevant Customer.
- Scroll down and click Edit .
- Select the Warehouse Managemen t tab and then the Purchase Order Products tab.
- Select **+Add Custom Field 1**.
- Enter a name for the Custom Field in the**Custom Field 1 Name**text box, such as Serial Number.
- Select a **Configuration Type** from the drop down. When you select a Configuration Type, the related settings will be selected. The behaviour of the settings will be explained in the blue text box on the side of the page.

Please note that the configuration type do not directly impact the behaviour of the custom fields, it is the settings that do. When you select a configuration type certain settings will be selected, however, this is just a template designed to simply the setup process. You can still change the settings even once you have selected a configuration type.

- The available Configuration Types and their behaviour is defined below:

| **Configuration Type** | **Behaviour** |
| --- | --- |
| Optional reference captured on inbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as an optional field that the user can record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   This custom field will display as a required custom field that the user must record a value against when picking stock for an outbound order.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |
| Optional Reference captured on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as an optional field that the user can record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   This custom field will display as a required custom field that the user must record a value against when picking stock for an outbound order.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |
| Required Reference captured on Inbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as a required field that the user must record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   If stock is already in the warehouse for this customer without a value recorded against this field then the user will be required to capture a value when picking.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |
| Required Reference captured on Inbound and Verified on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as a required field that the user must record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   If stock is already in the warehouse for this customer without a value recorded against this field then the user will be required to capture a value when picking.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp.   If a value is already captured against this field then the user will be required to scan or enter it when picking to verify that they have taken the correct stock. |
| Required Reference captured on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as an optional field that the user can record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   This custom field will display as a required custom field that the user must record a value against when picking stock for an outbound order.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |
| Serial Number captured on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as an optional field that the user can record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   This custom field will display as a required custom field that the user must record a value against when picking stock for an outbound order.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp.   If a value is already captured against this field then the user will be required to scan or enter it when picking to verify that they have taken the correct stock. |
| Serial Number captured on Inbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as a required field that the user must record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   If stock is already in the warehouse for this customer without a value recorded against this field then the user will be required to capture a value when picking.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |
| Serial Number captured on Inbound and Verified on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as a required field that the user must record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   If stock is already in the warehouse for this customer without a value recorded against this field then the user will be required to capture a value when picking.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp.   If a value is already captured against this field then the user will be required to scan or enter it when picking to verify that they have taken the correct stock. |
| SSCC captured on Inbound and Verified on Outbound      *(this configuration is only available if SSCC is enabled [Enabling and using SSCC/GS1 Label](https://help.cartoncloud.com/help/s/article/Enabling-and-using-SSCC-GS1-Labels))* | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as a required field that the user must record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   If stock is already in the warehouse for this customer without a value recorded against this field then the user will be required to capture a value when picking.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp.   If a value is already captured against this field then the user will be required to scan or enter it when picking to verify that they have taken the correct stock. |
| SSCC captured on Inbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as a required field that the user must record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   If stock is already in the warehouse for this customer without a value recorded against this field then the user will be required to capture a value when picking.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |
| SSCC captured or Verified on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as an optional field that the user can record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   This custom field will display as a required custom field that the user must record a value against when picking stock for an outbound order.   The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp.   If a value is already captured against this field then the user will be required to scan or enter it when picking to verify that they have taken the correct stock. |
| SSCC captured on Outbound | When recording a value against this custom field, the system will force the value to be unique among all onhand stock belonging to this customer. If a duplicate value is attempted to be captured, then an error will be displayed to the user to retry.      **Inbound Behaviour**   This custom field will display as an optional field that the user can record a value against when receiving stock into the warehouse.   The user can optionally generate new SSCC Barcode numbers for this field when receiving through the webapp.      **Outbound Behaviour**   This custom field will display as a required custom field that the user must record a value against when picking stock for an outbound order. The user can optionally generate new SSCC Barcode numbers for this field when picking through the webapp. |

- If you choose **Custom** as a Configuration Type you can then choose to select different settings. The settings are explained below.

| **Setting name** | **Description** |
| --- | --- |
| Enforce unique values | Enforce that each value recorded against the POP CF for that customer is unique. This means you can't record a value that is not unique against this custom field.    ******Please note that Customers active in multiple Warehouses, the unique value is not enforced across the different Warehouses. The unique value is enforced within each individual Warehouse for the Customer. |
| **Putaway / Inbound** |  |
| Enable Capture | Enable the field to be captured on the inbound process |
| Make this a required step | Make capturing this field on the inbound required. With this setting enabled users will be required to capture this field on the inbound process. |
| Split to lowest unit of measure | When receiving, stock will be split into single units of the lowest unit of measure configured against the product. |
| **Picking / Outbound** |  |
| Enable capture | Enable the field to be captures on the outbound process |
| Make this a required step | Make capturing this field on the outbound required. With this setting enabled users will be required to capture this field on the outbound process. |
| Split to lowest unit of measure | When picking, stock will be split into single units of the lowest unit of measure that is configured against the product. |
| Verify when picking | Enable this field to be verified upon picking the order. With this field enabled the custom field must be verified by the user upon picking it |
| Retain custom field 1 selection when performing sale order stock optimization | When the order is re-optimised the original custom field value will retain. This means when stock optimisation is conducted, CartonCloud will only look for stock with that same custom field value against it. For example, if the custom field is Batch Number and you want to ensure that once stock is assigned to an order with a certain Batch Number and you don't want that number changing during the stock optimisation, you would tick this option. |

- You will then need to select an Input Type. This is the type of data being recorded against the Custom Field. You have the below options when selecting your Input Type. The Input Type will not change per the Configuration Type. You will need to select the Input Type yourself.
  - **Alphanumeric**: using both letters and numerals
  - **Defined values (dropdown)**: define what values can be selected for the custom field
  - **Date:**a date field
  - **SSCC**: if using SSCC
- Regex definition can be set up using the [Regex Definitions](https://help.cartoncloud.com/display/KB2/Regex+Definitions) page. If a regular expression is set up then it will be used to extract the matched data when capturing the POP custom field on the CartonCloud mobile application.
- GS1 Barcode Field Identifier is required when using SSCC to specify the GS1 field identifier for the POP custom field. This will allow it to then be printed on the labels. See [Enabling and using SSCC/GS1 Labels](https://help.cartoncloud.com/help/s/article/Enabling-and-using-SSCC-GS1-Labels) for more information.
- If you wish to add another Custom Field, select the **+Add Custom Field** button below the existing Custom Field.
- Once all Custom Fields have been added, scroll down and select Save .

▶️ Follow along in the **WMS Basic Set Up Trail**...next up is [Introduction to Products Unit of Measure](https://help.cartoncloud.com/knowledge/introduction-to-products-unit-of-measure)[🎓](https://help.cartoncloud.com/knowledge/get-started-with-organisation-settings-warehouse)

---

<a id="setting-up-cartoncloud-for-wms-tms"></a>
## Setting up CartonCloud for WMS & TMS

_Source: https://help.cartoncloud.com/knowledge/setting-up-cartoncloud-for-wms-tms_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Basic Setup Trail.**Please ensure you have read [CartonCloud Outbound Process Explained](https://help.cartoncloud.com/knowledge/cartoncloud-outbound-process-explained) first.🎓

Nick is excited to start using CartonCloud’s WMS software and reap the benefits it will bring to the business, his staff and their customers. However, Coffee Warehousing and Distribution also operate a transport component, with almost 80% of their customer’s orders being delivered by their own drivers and fleet. As this is a sizable portion of their operations workflows and processes, Nick is interested to see how CartonCloud can assist.

The great thing for Nick is that CartonCloud also offers a transport management system that can be integrated with CartonCloud’s WMS, creating an automated and streamlined process from picking right through to delivering the order.

### What can CartonCloud’s integrated WMS and TMS achieve?

If you are using CartonCloud’s WMS and TMS, there are many features and benefits that will increase efficiency and reduce administrative tasks in your workflow.

Rather than doubling up on data entry or administrative tasks, you can choose to have a transport job (Consignment) automatically created from a Sale Order. You can also choose what status the Sale Order must reach before the corresponding Consignment is created. You may choose that once a Sale Order is packed, the Consignment is created, facilitating a seamless process from picking and packing the order to dispatch and delivery.

The Sale Order data is all transferred to the Consignment, including the delivery address and customer details. You can even set up product mappings so that what is packed on the Sale Order corresponds with what is listed on the Consignment.

For example, if you have a Sale Order containing a carton of coffee ice cream and in the WMS, you have this product listed as a product type of frozen, you can create mappings that will create a Consignment that has a frozen carton listed against it. This will save you and your staff time and improve visibility and data accuracy on what is being shipped.

Nick knows these features will benefit the business and its day-to-day operations. However, he is most excited that his customers will only have one invoice for all their transport and warehouse charges. This will save the team countless hours and make it much clearer and easier for its customers.

### How to set up WMS and TMS together?

You need to follow two key steps to ensure your account is set up correctly to use both WMS and TMS together. Follow along with Vincent as he steps through the process required to set up WMS and TMS together.

**📹 Video:** https://www.youtube.com/embed/FsR7vIlRmSU?list=PLxs2KBNumIq7ZzmdOtOesVwexXuSAiIYO

🎉 Congratulations! You have completed the WMS Basic Setup CartonCloud Academy Trail.

---

# CartonCloud Academy > WMS Charging

<a id="introducing-warehouse-charging"></a>
## Introducing Warehouse Charging

_Source: https://help.cartoncloud.com/knowledge/introducing-warehouse-charging_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**This is the first article in the trail.🎓

Welcome to the Warehouse Charging Trail! In this Trail, you will be guided through how to make the most of the CartonCloud warehouse charging system.

You will learn about the different types of charges you can apply, the different charging methods available and how all your rates are automatically calculated for you.

With CartonCloud’s warehouse rating system, you will never miss a handling charge or storage fee. CartonCloud automates storage rates and pick and putaway charges, creating a seamless and efficient charging experience for you and your customers.

There are several different types of charges applicable for different stages of the warehouse process. These charges include:

- Sale Order Charges (example: an extra charge if the Sale Order is marked as urgent)
- Purchase Order Charges (example: flat fee for creating a Purchase Order)
- Handling Charges (example: an inbound charge applied to every Purchase Order)
- Storage Charges (example: a per pallet storage charge)
- Adhoc Charges (example: a charge applied for pallet wrapping that is only applied for applicable orders)

All of these charges are customisable and are created from within the Rate Card. The diagram below helps to demonstrate where each of these charges is applied in the warehouse process.

![](https://help.cartoncloud.com/hs-fs/hubfs/wc%201-png.png?width=670&height=218&name=wc%201-png.png)

CartonCloud will use the Rate Card you have created for your customer to determine what and how rates are applied to orders. The rates are automatically calculated and then added to the customer’s invoice at the end of the invoice period (or during, depending on your invoice settings).

![](https://help.cartoncloud.com/hs-fs/hubfs/wc%202-png.png?width=670&height=503&name=wc%202-png.png)

Nick from Coffee Warehousing and Distribution is excited to start using CartonCloud’s warehouse rating system. Coffee Warehousing and Distribution previously had to calculate all their Customer’s charges manually, with their rates kept in different excel sheets and documents that sometimes were hard to keep track of. Therefore, there were sometimes rate discrepancies and customers questioning their invoices. Now that Coffee Warehousing and Distribution are using CartonCloud all the rates will be automatically calculated and applied to customers' invoices, avoiding the need for manual administrative tasks and increasing rating accuracy.

### Understanding Rate Cards

Rate Cards are fundamental to the warehouse rating system in CartonCloud. A Rate Card determines what prices your Customer will be charged for your Warehouse and/or Transport services. It also contains the settings that determine how the charges will be applied.

Every Customer in CartonCloud has a Rate Card associated with it. By default, the Rate Card associated will be the Default Rate Card; however, you will be able to change this.

Follow along with Brittany as she explains what a Rate Card is and how to create one in your CartonCloud account.

**📹 Video:** https://www.youtube.com/embed/E7Pi1zrFzOE?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

▶️ Follow along in the **WMS Charging Trail**...next up is [**Sale Order and Purchase Order Charges Explained**](https://help.cartoncloud.com/knowledge/sale-order-and-purchase-order-charges-explained) 🎓

---

<a id="introduction-to-handling-charges"></a>
## Introduction to Handling Charges

_Source: https://help.cartoncloud.com/knowledge/introduction-to-handling-charges_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**Please ensure you have read [**Sale Order and Purchase Order Charges Explained**](https://help.cartoncloud.com/knowledge/sale-order-and-purchase-order-charges-explained) first.🎓

The next type of charge we are going to look at is Handling Charges. Handling Charges are charges applied to incoming and outgoing orders and cover the costs associated with picking and putting away orders.

CartonCloud allows for flexibility with how you charge your handling rates by offering a number of different Putaway and Picking Charge Options. The Putaway and Picking Charge Option dictates how your handling charges are calculated.

Follow along with Brittany as she explains what handling charges in CartonCloud are and the different picking and putaway charge options available.

**📹 Video:** https://www.youtube.com/embed/UblWS0ubRno?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

For more information on Putaway and Picking Charge options please see [here](https://help.cartoncloud.com/knowledge/putaway-purchase-orders-and-picking-sale-orders-charge-options)

### Handling Charges and Aggregation

Now that you know the different handling charge methods available, we can take a deeper dive into one charge method in particular, the default method of ‘Scale to highest unit of measure’. This method will scale the products to the highest unit of measure and charge the handling rates in that manner. However, with this charge method you can choose to use different aggregation options. By default, no aggregation will apply, however, you do have the option of aggregating by SKU by location or by SKU across the entire warehouse.

Follow along with Brittany as she explains the different aggregation options and how they are applied.

**📹 Video:** https://www.youtube.com/embed/FCbCIO_Y31I?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

#### Aggregation options

| Picking Charge Aggregation Options | Explanation |
| --- | --- |
| Aggregate by SKU across the entire warehouse | Regardless of what location the products for a Sale Order are in, they will be aggregated |
| Aggregate by SKU by location | CartonCloud will aggregate all products for a Sale Order in the same location, regardless of whether they are from different POP records |
| No aggregation (default) | Products will not aggregate together |

### How to create a Handling Charge

Now that you know what a handling charge is and the different handling charge methods you can apply, it is time to start creating your handling charges!

Follow along with Brittany as she steps through how to create a handling charge.

**📹 Video:** https://www.youtube.com/embed/PitB-FnNEB4?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

### Handling Charges and Rounding

Let’s take a look at handling charges and rounding! When you are using the Default (Scale to Highest Unit of Measure) handling charge method for either Picking or Putaway you will need to select a Charge Behaviour (rounding option) and an aggregation option. We have already covered off aggregation so it is now time to look at rounding options.

Follow along with Brittany as she steps through how rounding applies when using the Scale to Highest Unit of Measure handling charge method.

**📹 Video:** https://www.youtube.com/embed/PZKj5awKcKY?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

▶️ Follow along in the **WMS Charging Trail**...next up is [**Understanding Adhoc Charges**](https://help.cartoncloud.com/knowledge/understanding-adhoc-charges) 🎓

---

<a id="introduction-to-storage-charges-and-storage-periods"></a>
## Introduction to Storage Charges and Storage Periods

_Source: https://help.cartoncloud.com/knowledge/introduction-to-storage-charges-and-storage-periods_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**Please ensure you have read [**Understanding Adhoc Charges**](https://help.cartoncloud.com/knowledge/understanding-adhoc-charges) first.🎓

The next category of charges we will be covering is storage charges. Storage charges cover the costs associated with storing products for your customers. Storage charges can sometimes be complex, however, are also very flexible allowing you to charge according to your customer and operational requirements.

Follow along with Brittany as she explains storage charges and storage periods.

**📹 Video:** https://www.youtube.com/embed/ONhZEF08OdI?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

### What is a storage period?

Storage Periods are the number of days at a time that you wish to charge storage for.

Storage Periods contain a start and end date and are created automatically within CartonCloud as soon as products are loaded into warehouse locations.

### What is a storage charge?

Storage charges apply to stock that is in the warehouse and allocated to a warehouse location. Storage Charges are automatically calculated and applied to invoices.

There are a number of different storage charging methods available, making storage charges flexible to your customer and operational requirements and ensuring you are charging your customers correctly.

Storage Charges incur for the entire storage period. For example, if a pallet is only in the warehouse for 1 hour and the storage period is a week, it will still be charged for 1 week of storage. In addition, for 'partial' products, storage is never reduced.

### Important points to note on storage charging:

- Storage charges are based on the product type of the stock in the warehouse location or the product type of that warehouse location. This is controlled from the rate card settings.
- Storage charge method set up for the rate must also be selected against the product that is being charged for that rate

Nick from Coffee Warehousing and Distribution is looking forward to setting up his customer’s storage charges and storage periods. Storage charges were previously calculated manually, Nick is looking forward to saving time and improving charging accuracy by automating the rate calculation process.

### Storage Charges and Storage Period Settings

Before we start creating storage charges you first need to ensure you have the correct storage charges settings configured from within the customer’s rate card.

Follow along with Brittany as she explains the different settings and how you can configure them from the rate card.

**📹 Video:** https://www.youtube.com/embed/kF_DjeyuIMk?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

Nick from Coffee Warehousing and Distribution is ready to start configuring his storage charges, however, he first needs to review the below settings, configure the settings in the appropriate rate cards and then he will be able to create his storage charges.

### Storage Charges Settings

| Setting Name | Description |
| --- | --- |
| Storage Charge Period Generation | The period for which you wish to charge storage. Storage is typically charged Weekly, but you could set this to a value such as 1 day to calculate storage charges daily. Other options include Monthly/Fortnightly and a new option of Disable if you require no storage to be charged. |
| Storage Starts On | Based on the selection of the Storage Charge Period, options are Day of the week (Mon-Sun for Weekly/Fortnightly) or Date of the Month (1-28 for Monthly) |
| Pallet Rental | If you charge clients an additional fee for Pallet Rental such as CHEP for example, this can be entered here. This fee will apply for every warehouse location that is in use for the Storage Charge Days nominated. e.g. if 7 then this pallet rental value will be charged once every 7 days. The pallet rental charges apply for every pallet in the warehouse for the customer/s associated with the rate card. |
| Double Charge Storage | New storage charges will be applied even if the location was charged for existing storage. This means that if a location was in use at the start of the storage period, and then new stock arrived and went into the same location, it'll be charged again as 'New Storage'. This also applies if the location was in use at the beginning of the storage period, then went empty (stock went out), and then more stock was put into the location. By enabling 'Double Charge Storage', you'll charge the location once for the existing product, and again for the new stock coming in. |
| Charge on Split | Charge storage immediately when splitting or partially moving stock. If disabled (default), stock which is split or partially moved inside the warehouse within a given storage period does not begin charging for those new locations until the next storage period begins. The locations will only begin charging on the next storage period and are labelled as "Existing" Storage. If this is enabled, split and partially moved stock commences storage charges as "New" storage immediately upon the movement in exactly the same way as new stock entering the warehouse for the first time would be charged as New storage. Note that full stock movements do not trigger additional storage, the additional charges will only come into play if the stock is split between two or more locations. |
| Charge Product Type Option | Both Products and Warehouse Locations have a product type which controls the Storage Rates used. If, for example, you have an ambient product but temporarily store it in a Chilled location, you would probably still want to charge the Ambient Rate. In this circumstance, the Charge Product Type should be set to 'Products', as the Products product type is used to determine the charges. However, if you operate a warehouse which is all ambient, but you charge differently for Racked Locations vs Block Stacking (for example), you would want to charge based on the Warehouse Locations Product Type, rather than the Products Product Type - as all products will be 'Ambient' but you may have some locations setup as 'Block Stack' or 'Racked'.  Products - Charge Storage based on the Products "Product Type"       Warehouse Location - Charge Storage based on the Warehouse Locations "Product Type"  Note: Not all Storage Charge Method take this setting into effect, for example, Item based Storage charges charge the same rate irrespective of the Product Type of the Warehouse Location the product is stored in. For a complete list of which charging methods are affected by this setting, refer to: [Rate Card - Storage Charges](https://help.cartoncloud.com/kb2/web-app-page-specific-support/administrator-pages/more/rate-cards/view-rate-card/rate-card-storage-charges) |
| Storage Period Minimum Charge | The minimum charge for a Storage Period. For example, if the minimum charge is set to $600, and all storage charges added together come to $500, then the minimum charge would push the total price up to $600. |
| Storage Period Free Days | The number of free days storage to give to stock. For example, if you set this to 3 and stock arrived into your Warehouse on a Monday, then storage would begin charging on the Thursday. See "[Setting the number of free days within a Storage Period](https://help.cartoncloud.com/kb2/web-app-procedures-troubleshooting/invoicing-charging-related/storage-periods-and-storage-charging/setting-the-number-of-free-days-within-a-storage-period)" for more info. |

Once Nick has reviewed the above settings he can now configure the settings in the appropriate Rate Cards. To do this he:

- Navigate to the relevant Rate Card, More > Rate Card .
- Select the relevant Rate Card.
- Click Edit .
- Scroll down to the bottom and find the storage charge settings.
- Update the settings as required and click Save.

Now that Nick has updated his storage charge rate card settings he is ready to start creating his storage charges. How to create a storage charge will be covered in the next unit.

▶️ Follow along in the **WMS Charging Trail**...next up is [**Understanding Storage Charge Methods**](https://help.cartoncloud.com/knowledge/understanding-storage-charge-methods) 🎓

---

<a id="other-charges"></a>
## Other Charges

_Source: https://help.cartoncloud.com/knowledge/other-charges_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**Please ensure you have read [**Understanding Storage Charge Methods**](https://help.cartoncloud.com/knowledge/understanding-storage-charge-methods)first.🎓

### Miscellaneous Charges

The next group of charges we will cover is Miscellaneous charges. Miscellaneous charges can be found within the Rate Card and are charges that may not be covered in your picking and putaway charges but are still relevant to your operations and how you wish to charge your customers.

Follow along with Brittany as she explains what Miscellaneous charges are.

**📹 Video:** https://www.youtube.com/embed/lXusuuSL71M?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

| **Charge** | Description |
| --- | --- |
| Per Invoice Administration Fee | An administration fee applied to every Invoice generated, this appears as a separate line item on the Invoice (separate from Freight, Warehousing, Storage etc). |
| Per Invoice Minimum Fee | A minimum amount applied to the whole invoice generated, if this amount is not met by the total invoice amounts, an additional charge amount will then be loaded to the invoice to bring the total charged on the invoice up to the amount specified here. |
| Warehouse Charges Minimum Fee | A minimum amount applied to the warehouse charges generated (this is Handling Pick Page Charges and Storage Charges), if this amount is not met by the total warehouse charges amount, an additional charge amount will then be loaded to the invoice to bring the total charged on the invoice up to the amount specified here. |

Nick will apply miscellaneous charges to his customer’s rate card, he believes the minimum charges and the per invoice admin fee will help ensure the company is profitable each time a customer is invoiced while also ensuring that customers are charged fairly and correctly.

### Manual Charges

The last charges we are going to look at are income charges. Income charges allow you to manually charge jobs at an individual order level. Income Charges can be applied to Consignments, Manifests, Purchase Orders, Sale Orders, Storage Periods, and Run Sheets.

Follow along with Brittany as she explains what income charges are and how to add an income charge.

**📹 Video:** https://www.youtube.com/embed/zBIIK8rZTWY?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

Nick is glad to know that CartonCloud’s rating system is flexible ad there is an option to add manual charges to orders that are outside the charges already configured. At Coffee Warehousing and Distribution some of the work they do for customers is a one off or out of sope of their usual services and rates, therefore, income charges will be an easy solution for these circumstances.

Income charges are only recommended if the charge is unique and is not a charge applied consistently. Repeated charges should only be applied using Adhoc Charges or charges set up in the Rate Card.

🎉 Congratulations! You have completed the WMS Charging CartonCloud Academy Trail.

---

<a id="sale-order-and-purchase-order-charges-explained"></a>
## Sale Order and Purchase Order Charges Explained

_Source: https://help.cartoncloud.com/knowledge/sale-order-and-purchase-order-charges-explained_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**Please ensure you have read [**Introducing Warehouse Charging**](https://help.cartoncloud.com/knowledge/introducing-warehouse-charging) first.🎓

Now that you know what a Rate Card is and how automatic charging in CartonCloud works, we can cover one of the first types of charges found within the Rate Card, Purchase Order and Sale Order Charges.

### What are Purchase Order and Sale Order Charges?

Purchase Order and Sale Order charges are charges applied to individual Sale Orders and Purchase Orders and are set up from within the Rate Card. There are various charges within the Purchase Order and Sale Order Charges section of the Rate Card, which will be covered in greater detail in the coming units. These charges help cover the costs of managing and creating orders for your customers.

### Where can Purchase Order and Sale Order Charges be found on the Rate Card?

- Navigate to the relevant Rate Card, More > Rate Cards .
- Select the relevant Rate Card.
- Select the Details tab.
- Under Warehouse Charges, you will see Sale Order and Purchase Order Charges.

![](https://help.cartoncloud.com/hs-fs/hubfs/wc%203-png.png?width=670&height=291&name=wc%203-png.png)

### How are Purchase Order and Sale Order Charges calculated?

Purchase Order and Sale Order Charges are applied on a per-order basis. For example, the Sale Order Charge is applied per Sale Order, and the Outbound SKU Charge is applied per order per the number of unique products on the order. The rates for these charges are taken from the Customer’s Rate Card, automatically applied to the orders and then added to the Customer’s Invoice.

### Creating Purchase Order Charges

Purchase Order charges cover the costs associated with creating and managing Purchase Orders in your warehouse. There are a number of different Purchase Order Charges you can apply to your Customer’s Rate Card and consequently your Customer’s Purchase Orders.

Follow along with Brittany as she explains how to create a Purchase Order Charge in your Customer’s Rate Card.

**📹 Video:** https://www.youtube.com/embed/5Sietm-MKcs?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

### Purchase Order Charge Scheme

Before you create your Purchase Order Charges you need to first select your Purchase Order Charge Scheme. The Purchase Order Charge Scheme determines how your Purchase Order Charges are configured and calculated. You have two different schemes to choose from:

- Standard: charges per order fees.
- Percentage of value: charges percentage of the Purchase Order value. For example, if the value of a Purchase Order is $200 and you have a percentage of value percentage of 10%, the charge would be $20.

The charge scheme that you select will determine what charges are available for you to configure for your Purchase Order.

#### (Standard) Purchase Order Charges

| Charge Name | Charge Explanation |  |
| --- | --- | --- |
| Purchase Order Charge | A per order administration fee. This charge is applied to every Purchase Order. |  |
| Inbound Invoice Upload Charge | Charge for uploading an invoice file or document to the Purchase Order. |  |
| Urgent Order Charge | The additional charge to be applied to the order if the customer select that the order is urgent. |  |
| Purchase Order Minimum Charge | The minimum charge for a Purchase Order. For example, if the minimum charge is $10 and all other charges added together come to $7 then the minimum charge would be applied and the charges would come to $10. |  |

#### (Percentage of value) Purchase Order Charge

| Charge Name | Charge Explanation |
| --- | --- |
| Purchase Order Charge Percentage | This is the percentage of the Purchase Order value that should be charged. The value of the Purchase Order is recorded against the Purchase Order in the Purchase Order Value field. |

### Creating Sale Order Charges

Sale Order charges cover the costs associated with creating and managing Sale Orders in your warehouse. There are a number of different Sale Order Charges you can apply to your Customer’s Rate Card and, consequently your Customer’s Sale Orders.

Follow along with Brittany as she explains how to create a Sale Order Charge in your Customer’s Rate Card.

**📹 Video:** https://www.youtube.com/embed/-mfogkK-FY8?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

### Sale Order Charge Scheme

Before you create your Sale Order Charges, you need to first select your Sale Order Charge Scheme. The Sale Order Charge Scheme determines how your Sale Order Charges are configured and calculated. You have two different schemes to choose from

- Standard: charges per order fees.
- Percentage of value: charges percentage of the Sale Order value. For example, if the value of a Sale Order is $200 and you have a percentage of value percentage of 10%, the charge would be $20.

#### (Standard) Sale Order Charges

| Charge Name | Charge Explanation |
| --- | --- |
| Sale Order Charge | A per order administration fee. This charge is applied to every Purchase Order. |
| Urgent Order Charge | The additional charge is to be applied to the order if the customer selects that the order is urgent. |
| Outbound SKU Charge | The charge for each different SKU (different product) added to the Sale Order.  For example, picking 100 cartons of one product would most likely be faster than picking 20 cartons for 5 different products. Therefore, by implementing an SKU charge, you are covering for the extra time and effort required for products with more than one SKU. The SKU charge is counted as the number of different products added to the order.  The number of unique products x outbound SKU charge = SKU charges |
| Minimum SKU Charge | The minimum SKU charge is implemented when the SKU charge does not meet the minimum. The Minimum SKU charge is applied per product. |
| Sale Order Minimum Charge | The minimum charge for a Sale Order. For example, if the minimum charge is $10 and all other charges added together come to $7 then the minimum charge would be applied, and the charges would come to $10. |

#### (Percentage of value) Purchase Order Charge

| Charge Name | Charge Explanation |
| --- | --- |
| Sale Order Charge Percentage | This is the percentage of the Sale Order value that should be charged. The value of the Sale Order is recorded against the Sale Order in the **Sale Order Value**field. |

The charge scheme that you select will determine what charges are available for you to configure for your Sale Order.

▶️ Follow along in the **WMS Charging Trail**...next up is [**Introduction to Handling Charges**](https://help.cartoncloud.com/knowledge/introduction-to-handling-charges) 🎓

---

<a id="understanding-adhoc-charges"></a>
## Understanding Adhoc Charges

_Source: https://help.cartoncloud.com/knowledge/understanding-adhoc-charges_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**Please ensure you have read [**Introduction to Handling Charges**](https://help.cartoncloud.com/knowledge/introduction-to-handling-charges) first.🎓

The next type of charges we will be covering are Adhoc Charges. Adhoc Charges are customised charges that cover costs associated with work and activities that are adhoc in nature and will therefore, not apply to every order every time. Follow along with Brittany as she explains what an Adhoc Charge is.

**📹 Video:** https://www.youtube.com/embed/Qp4zcKYTOMs?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

### What are Adhoc Charges

Adhoc Charges are customised charges that allow you to add on charges to orders that may not apply to every job. For example, you may create an Adhoc Charge for Demurrage (waiting time), Hand Unload, and Labelling work. Adhoc Charges can apply to all Customers, be customer-specific or be customised for an individual order.

Adhoc charges are created to be available across the entire organisation and then further adjusted within each of your [Customer's Rate Cards](https://help.cartoncloud.com/display/KB2/View+Rate+Card). For example, you can have an Adhoc Charge for Pallets Wrapped, but set a price of $3 a pallet for Customer A and $4 a pallet for Customer B. This would be achieved by adjusting the Adhoc Charge within each Customer's respective rate card.

### Benefits of Adhoc Charges

- Allows for flexibility in how you charge your customers
- Ensures all costs are covered, including charges that you may not have originally foreseen
- Allows customisation in how you charge your customers
- Avoids manual work of writing down extra charges that may need to be applied
- Removes the responsibility on people remembering what extra charges need to be applied as you can record adhoc charges at the time of handling the order

### Use cases of Adoc Charges

- Demurrage (waiting time)
- Hand Unload
- Labelling work
- Packaging

Nick from Coffee Warehousing and Distribution will be able to utilise adhoc charges to cover extra costs for labelling and packaging work they complete for their customers. They also unpack containers at their site and will be able to use adhoc charges to charge their customers for this work.

### How to add an Adhoc Charge

Now that we have an understanding of Adhoc Charges and Adhoc Charge Groups we can cover  how to create an Adhoc Charge. Follow along with Brittany as she talks through how to create an Adhoc Charge in your CartonCloud account.

**📹 Video:** https://www.youtube.com/embed/_AvZ9CJD-7A?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

### How to apply an Adhoc Charge

Once you have created your Adhoc Charges you then need to apply them to the orders they are applicable for. Follow along with Brittany as she explains how to apply Adhoc Charges.

**📹 Video:** https://www.youtube.com/embed/_Xaers9F8Pk?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

▶️ Follow along in the **WMS Charging Trail**...next up is [**Introduction to Storage Charges and Storage Periods**](https://help.cartoncloud.com/knowledge/introduction-to-storage-charges-and-storage-periods) 🎓

---

<a id="understanding-storage-charge-methods"></a>
## Understanding Storage Charge Methods

_Source: https://help.cartoncloud.com/knowledge/understanding-storage-charge-methods_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Charging Trail.**Please ensure you have read [**Introduction to Storage Charges and Storage Periods**](https://help.cartoncloud.com/knowledge/introduction-to-storage-charges-and-storage-periods) first.🎓

### Per location and per location (and bulk location pallets)

The first storage charge method we are going to cover is per location and per location (and bulk location pallets).

Follow along with Brittany as she explains how these two storage charges work.

**📹 Video:** https://www.youtube.com/embed/ybsVT-0CUog?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

These two storage charge methods are quite similar, however, they have a few key differences. Each storage charge method is summarised below:

| Storage charge method | Description |
| --- | --- |
| Per Location (default) | Storage charges are calculated based on the number of Warehouse Locations that are used. In the case where multiple products are stored on a single pallet, the system will just charge the location once. Bulk locations may be used to store multiple 'pallets' in a single location and therefore charge multiple pallets of storage. Per-Location charges do not take into account the quantity of product in a location, simply the number of unique locations used. |
| Per Location (and bulk location pallets) | Calculated similarly to Per-location (default), however, the product quantity is taken into account when calculating storage charges. This means large quantities of stock can be loaded into locations without being split into individual pallets.  Notes:  Both Single Pallet and Multiple Pallet locations take quantity into account, meaning if you load 2 Pallets worth of stock into a Single Pallet Location (which isn't possible, but the software allows this to happen), then it'll charge 2 x pallets for that location. The determination of the Number of Pallets comes from the "[Oversize Unit](https://help.cartoncloud.com/kb2/web-app-page-specific-support/administrator-pages/warehouse/products/products-units-of-measure#ProductsUnitsofMeasure-OversizeWarning)".  Single Pallet Locations:  If you are using this charging method for single pallet locations, CartonCloud will default by the number of pallets in the location (even if this exceeds one). However, if you wish only to allow one charge for each location, you can change this from the [Organisation Settings](https://help.cartoncloud.com/kb2/web-app-page-specific-support/administrator-pages/more/organisation-settings). The option is called:  "If "Per Location (and bulk location pallets)" Storage Charges are used - Should all stock on Single Pallet Locations be combined into a single charge?"  No (Default) - The location can be charged once for each SKU stored. For example, a client storing 4 different products on a Single Pallet Location will be charged for the location 4 times. If stock quantities greater than 1 pallet are loaded onto the location, (ie: a product is configured as 40 boxes per pallet, and 45 boxes are loaded into the location), the location will be charged for the number of pallets stored, ie: 2 pallets.  Yes - All stock on a Single Pallet location is combined into a single charge. For example, a client storing 4 different products on a Single Pallet location will only be charged for the location once. If stock quantities greater than 1 pallet are loaded onto the location, (ie: a product is configured as 40 boxes per pallet, and 45 boxes are loaded into the location), the location will still only be charged once. |

Nick from Coffee Warehousing and Distribution is evaluating if he will use this storage charge method. Most of his warehouse locations are racked so Per location would work for him. However, he doesn’t have any bulk locations so he probably wouldn’t use per location (and bulk location pallets). Nick is going to take a look at the other storage charge methods available before he makes his decision.

If you are going to use per location or per location (and bulk location pallets) storage charge method you need to ensure the below is set up before creating the charge:

- The products using this charge have the charge method selected against the product (in the product settings).
- The product type set against the charge matches the product type set against the product

### Volume Based and Weight Based

The second storage charge method we are going to cover is volume based and weight based.

Follow along with Brittany as she explains how these two storage charges work.

**📹 Video:** https://www.youtube.com/embed/W56cNjorPP0?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

| Storage charge method | Description | Set up requirement |
| --- | --- | --- |
| Volume Based | It is calculated based on the total amount of product volume in the warehouse during the given time period. The number of warehouse locations used does not impact the storage charges. | To utilise Volume Based storage charge method, you will first need to configure the Product settings:  Navigate to the Products page, Warehouse>Products. Select the applicable Product. Scroll down to Storage Charge Method and select Volume Based. Within the Product Volume (in Cubic Meters) box, enter the volume.  Select the green Save button. |
| Weight Based | It is calculated based on the total amount of product weight in the warehouse during the given time period | To utilised Weight Based storage charge method, you will first need to configure the Product Settings:     Navigate to the Products page, Warehouse>Products. Select the applicable Product. Scroll down to Storage Charge Method and select Weight Based. Within the Product Weight (in Kilograms) box, enter the weight. Scroll down and select Save. |

Weight based storage charge method can be utilised when storing larger and heavier items. For example, steel or drums of liquid that are sold in litres rather than in bottles.

Volume based storage charge method is best utilised when wanting to accurately track the actual storage space being utilised. Nick from Coffee Warehousing and Distribution doesn’t think this suits the way he charges his customers or the types of product they store.

However, if utilising this storage method ensure you have set up the product weight and/or volume at the product settings, the products using this charge have the same charge method selected (in the product settings) and the product type set against the charge matches the product type set against the product.

### Per Pallet (Based on Quantity)

The next storage charge method we are going to cover is per pallet.

Follow along with Brittany as she explains how per pallet storage charge works.

**📹 Video:** https://www.youtube.com/embed/1qsFO_-nXSI?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

Per pallet (based on quantity) is a popular storage charge method as it is an effective way to accurately track the actual storage space being utilised. However, this storage charge method can only be applied for products that have pallet conversions. Therefore, if the product you are storing does not have pallet conversions, you would use a different storage charge method. With per pallet (based on quantity) storage charge method, it is important to note that the total quantity of each product is aggregated across all warehouse locations and then the number of pallets are calculated and rounded up to the nearest whole number.

Nick from Coffee Warehousing and Distribution would like to use this storage charge method for one of his customers as they have product pallet conversions set up for their products and use pallets to store their goods. Nick reads over the following set up requirements to make sure the products are set up correctly to use this storage charge method:

| Storage charge method | Description | Set up requirements |
| --- | --- | --- |
| Per pallet (based on quantity) | The total quantity of each Product is aggregated across all warehouse locations, and then the number of pallets are calculated and rounded up to the nearest whole number. Finally, the unit of measure conversion for the pallet quantity is utilised to determine the number of pallets. For example, if 6 cartons = 1 pallet and you have 8 cartons of one product for a storage period, CartonCloud will round up and charge 2 pallets for that storage period. | To utilise the Per Pallet (based on quantity) storage charge method, you must first set up the Product Unit of Measure for pallet for each applicable Product using the charging method and the pallet conversions. Click [here](https://help.cartoncloud.com/x/EAO_Hw) for instructions on how to set up the Product Unit of Measure. The products using this charging method must have Per Pallet (based on quantity) selected as the storage charge method in the product settings. |

Now that Nick knows how Per Pallet (based on quantity) storage charge method works and has set up his products accordingly he is ready to start creating his storage charges. How to create storage charges will be covered in the upcoming units.

### Per Unit of Measure

The next storage charge method we are going to cover is per unit of measure.

Follow along with Brittany as she explains how per unit of measure storage charge works.

**📹 Video:** https://www.youtube.com/embed/OH4yW8NnXUE?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

Per unit of measure storage charge method calculates storage rates for products based on the Unit of Measure specified. This is similar to per item storage charging, however, you can have different charges for each different Unit of Measure. This method is helpful if you wish to charge storage to your customers by only one Unit of Measure (using the round up or down to Unit of Measure functionality) or if you would like to have different charges for each Unit of Measure.

### Creating a Storage Charge

Now that you know what a storage charge and a storage period is, how to configure the storage settings and the different storage charge methods, it is time to create a storage charge!

When you create a storage charge there are a few things you need to consider to ensure the charge is set up correctly and you avoid charge errors in the future.

You will need to select a storage charge method when you create your storage charge. If you still are unsure on what storage charge method you would like to utilise please go back to the previous units to revise.

Follow along with Brittany as she steps you through how to create a storage charge in your customer’s rate card.

**📹 Video:** https://www.youtube.com/embed/sSDgc5ffklk?list=PLxs2KBNumIq4x4VrcAZTWIRFv2LtrxLes

Nick is now ready to start creating storage charges to ensure all storage costs are covered and he is charging and invoicing his customers correctly.

▶️ Follow along in the **WMS Charging Trail**...next up is [**Other Charges**](https://help.cartoncloud.com/knowledge/other-charges)🎓

---

# CartonCloud Academy > WMS Mobile App

<a id="introducing-scan-move"></a>
## Introducing Scan Move

_Source: https://help.cartoncloud.com/knowledge/introducing-scan-move_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Mobile App Trail.**Please ensure you have read [Introducing Wave Picking on the mobile app](https://help.cartoncloud.com/knowledge/introducing-wave-picking-on-the-mobile-app) first.🎓

### What is Scan Move?

The last mode on the warehouse mobile app we have to cover is Scan Move. Scan Move allows you to easily move stock from one location to another by either scanning or manually entering a label barcode. It provides details of every record included in the move and allows you to view all records currently recorded against a particular location or pallet. In addition, you can move part quantities from a location (as opposed to moving all stock within the location) or a select quantity of product (rather than the entire POP record).

Follow below as Vincent introduces Scan Move and explains the functionality it offers.

**📹 Video:** https://www.youtube.com/embed/a89yyZYWiiM?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### Use cases/benefits of using Scan Move

- Provides visibility and details on what is being moved.
- It can be used to check and confirm what stock is associated with the scanned or entered label barcode.
- Increased accuracy when using the confirmation step (double scanning the new location barcode or selecting Move on the screen to confirm the move).

Nick, from Coffee Warehousing and Distribution, is excited to start using Scan Move in his warehouse. He knows his staff will find the feature extremely useful, especially having the ability to scan a location and see all products in that location.

### Scan Move - Basic Move

Now that you know what Scan Move is; it is time to learn how to complete a move using Scan Move. To begin with, we will step through how to complete a basic move using Scan Move.

Follow along with Vincent as he steps through completing a basic move using Scan Move.

**📹 Video:** https://www.youtube.com/embed/CoH9KFBI8Kw?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

Nick is ready to start using Scan Move in the Coffee Warehousing and Distribution warehouse; however, before he does so, he checks the list below to ensure he is ready to go.

#### Checklist before using Scan Move

- You will need to use a Mobile device (either a Mobile Phone (iOS or Android) or a Mobile Computer ) to access Scan Move.
- If you use a Bluetooth Barcode Scanner , ensure it is connected and working correctly. See Connect a Bluetooth Barcode Scanner for more information.

#### Scan Move History

Follow along with Vincent as he steps through using Scan Move History.

**📹 Video:** https://www.youtube.com/embed/yv0Tngs56QI?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### Scan Move - Move Cart

So far, you have only seen Scan Move being utilised for moving full quantities; however, it also has the ability to move part quantities using the Move Cart. The Move Cart almost acts like an actual move cart in your warehouse. You can take stock from one location, continue moving through the warehouse, and then take stock from another locati before moving it into a new location.

Nick knows his staff will be using the Move Cart for a number of different situations and processes in the warehouse. Some use cases Nick already knows the team will be able to use the Move Cart for include:

- Replenishing pick face locations.
- Consolidating warehouse locations to make room for new stock.
- Putting away unassigned stock.

#### How to enable the Move Cart

- Once on the Scan Move screen, enable the Move Cart by sliding the Use Move Cart toggle.

#### How to use the Move Cart with multiple items

Follow along with Vincent as he demonstrates how to use the Scan Move Move Cart when you need to add multiple items from different locations and move them to numerous different locations.

**📹 Video:** https://www.youtube.com/embed/YF8Fr2sf2Dc?&list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD&index=13&wmode=opaque&rel=0

#### How to use the Move Cart to split quantities

In the following video, Vincent steps through how to use the Move Cart to split a product quantity and then print a new label.

**📹 Video:** https://www.youtube.com/embed/8buR04GWHrQ?&list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD&index=14&wmode=opaque&rel=0

#### Move Cart Benefits

Nick can see the benefits Scan Move, and in particular, the Move Cart will bring about to Coffee Warehousing and Distribution's processes and operations. Some of these benefits include:

- Ability to move multiple products from multiple different locations in one movement.
- Ability to split product quantities and move only partial quantities.
- Ability to print product labels after moving the stock.

🎉 Congratulations! You have completed the **WMS Mobile App Trail** CartonCloud Academy Trail.

---

<a id="introducing-the-warehouse-mobile-app"></a>
## Introducing the warehouse mobile app

_Source: https://help.cartoncloud.com/knowledge/introducing-the-warehouse-mobile-app_

🔔 Note: this is article is part of the **CartonCloud Academy - WMS Mobile App Trail.**This is the first article in the Trail.🎓

Welcome to the WMS Mobile App Trail! In this Trail, you will learn about the CartonCloud warehouse mobile application and how to use it in your operations. CartonCloud’s mobile application is purposely designed to complement and work in conjunction with the web application to support the agile and on the go work of warehousing and transport. In this Trail, we will focus on the warehouse features, and the transport features will be covered in the TMS Mobile App Trail.

Nick is the Manager at Coffee Distribution and Warehousing. Coffee Distribution and Warehousing store and deliver coffee beans for several different customers. Nick is in charge of setting up CartonCloud for the company. He has completed the set-up on the web application for transport and warehouse. He is excited to look at how he can use the mobile application to enhance his warehouse and transport processes further!

CartonCloud’s warehouse mobile app is designed to increase efficiency in inventory identification, stock movement and picking from the warehouse floor. In addition, the CartonCloud mobile app can connect with barcode scanners and printers to optimise and streamline warehouse operations and processes. The key features and benefits of the mobile warehouse application are listed below.

### Warehouse Mobile App Features

- Receiving and verifying a Purchase Order
- Putting away a Purchase Order (into a warehouse location)
- Splitting a Purchase Order
- Moving stock to different warehouse locations
- Checking what stock is in each warehouse location
- Picking a Sale Order
- Wave Picking
- Scanning to confirm the quantity, batch number or any other specified information (done by creating custom fields)
- Print labels

### Warehouse Mobile App Benefits

- Improved picking accuracy
- Increased visibility
- Facilitates greater efficiency in the putaway and picking process
- Enables the warehouse worker to be mobile in the warehouse but still have access to CartonCloud data and functionality
- Improved data accuracy
- Real-time data and information for customers
- Reduced manual and admin tasks
- Allows you to record information relating to the order at the e.g.e (e.g. extra charges or receiving a damaged pallet)

**📹 Video:** https://www.youtube.com/embed/nqbpnA7lrBk

### Navigating the mobile app

Before Nick starts using the mobile app in his warehouse operations, he needs to ensure everything is set up correctly and that he and his staff know how to navigate and use the app in their warehouse. To prepare for using the mobile app, Nic follows the below steps.

Follow along Vincent, as he introduces the warehouse mobile app and explains how to navigate the app.

**📹 Video:** https://www.youtube.com/embed/Dm1gBzjslNo?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### Downloading the mobile application

The first step in using the mobile application is downloading it onto your device! You can download the CartonCloud app onto either your iOS or Android device. The application can be downloaded from the [Apple App Store (for iOS)](https://itunes.apple.com/au/app/cartoncloud/id977857739?mt=8) or the [Google Play Store (for Android)](https://play.google.com/store/apps/details?id=com.cartoncloud.transport&hl=en).

![](https://help.cartoncloud.com/hs-fs/hubfs/1-1-gif.gif?width=787&height=1600&name=1-1-gif.gif)

### Logging in

Once you have downloaded the CartonCloud application and opened it on your device, you will be prompted to log in. Use the same login credentials you use for the CartonCloud web application.

You will need to ensure you have the [user role](https://help.cartoncloud.com/x/PAOYHw) Packer [enabled against your user](https://help.cartoncloud.com/x/LgOYHw)to be able to access the mobile app with your login.

Follow along with the below video for steps on how to login into the CartonCloud mobile app.

**📹 Video:** https://www.youtube.com/embed/NVFBfgLEiW4?&wmode=opaque&rel=0

### Pair it with a scanner!

If you are using an iPhone or Android phone, pair it with a [Bluetooth barcode scanner](https://help.cartoncloud.com/x/iAK-I) to enable barcode scanning when using the Cartoncloud app. If you are using or would like to use a mobile computer (which has an inbuilt scanner), you can check out [this](https://help.cartoncloud.com/x/iAK-I) page for recommended devices.

### Switch Mode

Once you have logged into the mobile app, you must select a [Mode](https://help.cartoncloud.com/x/CwmYHw). Each Mode offers different functionality and accommodates for a different warehouse process.

The four different warehouse Modes are:

| **Putaway** | allows you to receive, verify and putaway Purchase Orders. |
| --- | --- |
| **Picking** | enables you to pick Sale Orders. |
| **Picking 2.0** | enhanced functionality for picking Sale Orders. The new Picking 2.0 mode has numerous additional features to the stadard picking mode. It is suggested you utilise the Picking 2.0 mode. |
| **Wave Picking** | complete wave picks, and print wave pick labels. |
| **Scan Move** | scan warehouse locations, POP labels or pallet labels to move stock into new locations or print labels. Scan the warehouse location to check stock levels. |

![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Dec-02-2025-05-12-08-8176-AM.jpeg?width=280&height=559&name=image-png-Dec-02-2025-05-12-08-8176-AM.jpeg)

To access the User Modes selection page, use the hamburger menu icon. From here, you can select Switch Mode.

![](https://help.cartoncloud.com/hs-fs/hubfs/1-2-png.png?width=273&height=548&name=1-2-png.png)

You can also access the CartonCloud mobile app Settings and Notifications or refresh your current page.

### Settings

From the [Settings](https://help.cartoncloud.com/x/BQmYHw) page, you can:

| ABOUT | See what version of the application you are currently operating. We are consistently updating the application for performance improvements and new features, so ensure you [always operate the latest version of the app](https://help.cartoncloud.com/x/M4LWIQ)! |
| --- | --- |
| ORGANISATION | The CartonCloud tenancy you are in (tenancy is your CartonCloud account). |
| WAREHOUSE | The Warehouse you are in. If you have multiple warehouses, you will have a drop-down arrow to select the relevant warehouse you wish to be in. You will need to ensure the user has access to the warehouse to see the warehouse in the drop-down menu. |
| USER SETTINGS | [Enable Push Notifications](https://help.cartoncloud.com/x/LwqYHw) Show Consignment Origin/Show Additional Pickup / Delivery Info (transport only) [Enable Rapid Sale Order Packing](https://help.cartoncloud.com/x/sAuYHw) |
| DEFAULT MAP FOR NAVIGATION | Transport only |
| SUPPORT | [Send Diagnostics](https://help.cartoncloud.com/x/uwiYHw) |

![](https://help.cartoncloud.com/hs-fs/hubfs/f0402505c5b334cf53d24fa55e9b5cc2_a-55-bdccf-de-41-453-a-8351-ffe-86782064-f-png.png?width=332&height=664&name=f0402505c5b334cf53d24fa55e9b5cc2_a-55-bdccf-de-41-453-a-8351-ffe-86782064-f-png.png)

Now that Nick understands how to set up the mobile application, he uses the checklist below to ensure he has everything ready to start using the warehouse app.

### Checklist before using the mobile app

- Do you have devices to use the application on? (this could be as simple as an iPhone or Android mobile device or something more robust such as a mobile computer. See this page for recommended devices)
- If using a mobile device, do you have bluetooth barcode scanner to connect the phone to? (See this page for more information)
- Have you downloaded the application onto your device from either the Apple App Store or Google Play Store?
- Have you added a Packer User Role to the relevant Users in CartonCloud?
- Do the relevant Users have access to the warehouse they are working in?

▶️ Follow along in the **WMS Mobile App Trail**...next up is [Putaway Process on the mobile app (Purchase Orders)](https://help.cartoncloud.com/knowledge/putaway-process-on-the-mobile-app-purchase-orders)🎓

---

<a id="introducing-wave-picking-on-the-mobile-app"></a>
## Introducing Wave Picking on the mobile app

_Source: https://help.cartoncloud.com/knowledge/introducing-wave-picking-on-the-mobile-app_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Mobile App Trail.**Please ensure you have read Picking process on the mobile app (Sale Orders) first.🎓

Wave Picking is a way of picking multiple Sale Orders simultaneously. Wave Picking can increase picking efficiency and allow you to allocate specific Sale Orders for picking to particular staff members.

In the below video, Vicent introduces you to Wave Picking with CartonCloud.

**📹 Video:** https://www.youtube.com/embed/c7ierwGo88w?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### How to create a Wave Pick?

Wave Picks are created on the CartonCloud web app and can then be executed using either the web app or the mobile app. It is recommended that you use the mobile app for the most efficient way of completing the Wave Pick.

There are two ways in which you can create a Wave Pick, either by the Customer or for a selected Run Sheet. Selecting the Wave Pick type is the first step when creating a Wave Pick. Use the below links for detailed instructions on creating a Wave Pick for each Wave Pick type.

[Creating a Wave Pick for a single Customer](https://help.cartoncloud.com/display/KB2/Creating+a+Wave+Pick+for+a+single+Customer)

[Creating a Wave Pick for a Run Sheet](https://help.cartoncloud.com/display/KB2/Creating+a+Wave+Pick+for+a+Run+sheet)

### Wave Pick Process Types

Nick from Coffee Warehousing and Distribution is interested in Wave PIcking and is considering implementing this technique of picking Sale Orders into the warehouse processes. Firstly, Nick looks at some of the types of Wave Picks to see which would best suit his operational setup and processes.

There are three different workflows a Wave Pick can follow.

- Combined Wave Pick
- Split Pick and Pack
- Bulk Pick
- Pick to Tote

It is important to select the correct Wave Pick process type for your operation as each is designed for different workflows. We will step through each Wave Pick process type in the next units.

### Accessing Wave Picking on the Mobile App

- Select Wave Picking from the Switch Mode screen.

### Combined Wave Picks

The first Wave Pick process type we will cover is Combined Wave Pick.

Combination Wave Pick allows multiple Sale Orders to be grouped by a specific Customer or Run Sheet. This is the same way a Sale Order is usually picked and packed; however, it provides a way for orders to be grouped and then assigned to pickers. The Wave Pick can be assigned to the picker by naming the Wave Pick by the picker's name.

In the below example, the 3PL has multiple pickers to which they assign wave picks. The pickers will complete both the pick and pack process as they move through the Warehouse.

Nick from Coffee Warehousing and Distribution believes this type of Wave Pick would work well in his operation, especially on days when the warehouse receives a large number of orders. Nick will be able to easily allocate orders to be picked to certain pickers,  allowing them to focus on the jobs they have been assigned to.

#### How to pick a Combined Wave Pick on the mobile app

Follow along with Vincent as he steps through picking orders using a Combined Wave Pick on the mobile app.

**📹 Video:** https://www.youtube.com/embed/piDARw1m8FY?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### Split Pick and Pack Wave Pick

The next Wave Pick process type we will cover is Split Pick and Pack. Split Pick and Pack allows you to pick orders simultaneously by the product rather than order-by-order, and it separates the picking and packing process.

Once picking is completed, the user will be prompted to then pack each Sale Order individually; however, this will not necessarily be the same user. In some cases, the pick and pack process may be split, in which case the packer will take over the wave pick once the picking is complete. This is useful when picking and packing occur at two different locations in the warehouse or are completed by a different user.

Nick from Coffee Warehousing and Distribution believes this will work well in the warehouse as they have a separate area where packing occurs and two teams, one for picking and one for packing. If the team decide to use Split Pick and Pack Wave Picks, pickers will be able to pick all orders by the product and then move the goods to the packing area, where another team will pack the orders (using the Wave Pick) to have the orders ready for dispatch.

This workflow is demonstrated in the below Soft Drink 3PL  example:

#### How to pick and pack orders using Split Pick and Pack Wave Pick

Follow along with Vincent as he steps through picking orders using a Split Pick and Pack Wave Pick on the mobile app.

**📹 Video:** https://www.youtube.com/embed/PHns_gC-QKY?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### Bulk Wave Pick

The next Wave Pick process type we will cover is Bulk Pick. When using Bulk Pick, you will be picking orders simultaneously by the product rather than order-by-order. This is especially useful if there are limited pick-face locations to pick from and forklifts are required to pick the products.

Once an order is marked as picked the Sale Order will be updated to the 'Packed' status. When using this workflow, the picking and packing processes are combined into one. Once the orders are picked, they will be moved out of the Warehouse. For example, the orders are moved to a dock or delivery truck, where they will be sorted for delivery using their labels.

In the example below, a soft drink 3PL uses Bulk Wave Pick by the Run Sheet. They will pick all the different orders (by the soft drink type, not the Sale Order) and load them into the delivery truck. As the driver delivers the goods, he will complete the 'packing' process by sorting the soft drinks by the order using their labels.

Nick from Coffee Warehousing and Distribution isn’t sure if their operations will be using this Wave Pick process type as it doesn’t quite fit their operations; however, he is still interested to learn more about how the Wave Pick works.

#### How to complete a Bulk Wave Pick on the mobile app

Follow along with Vincent as he shows you how to complete a Bulk Pick Wave PIck on the mobile app.

**📹 Video:** https://www.youtube.com/embed/sL7cdoqOjtk?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

### Pick to Tote

The next Wave Pick process type we will cover is Pick to Tote. Pick to Tote streamlines warehouse efficiency by enabling pickers to fulfil multiple orders simultaneously, sorting items directly into totes as they navigate the warehouse.

Pick to Tote is included in all warehouse plans, however, [Wave Pick Auto Generation (Advanced Automation](https://help.cartoncloud.com/help/s/article/Advanced-Automation-Wave-Picks)which enables automated wave pick generation is only included within [WMS Premium](https://help.cartoncloud.com/help/s/article/WMS-Premium). Please reach out to our team [here](https://help.cartoncloud.com/help/s/contactsupport) if you would like more information on WMS Premium.

#### Pick to Tote Workflow Overview

Pick to Tote is a picking workflow designed to reduce the time spent picking. This is achieved by allowing pickers to pick multiple orders (usually 10-30) simultaneously, sorting them into totes as they go. This reduces the total walking time through the warehouse and the speed of the picking process. After picking, the trolley containing the totes is wheeled back to a packing station where the packing is completed.

![](https://lh7-rt.googleusercontent.com/docsz/AD_4nXfD8T6Sm25xN6_zTT5LOyxFHKGS8MsqK7dF0a8etu_rZthwpWc9ID2P8sAFNtFULMSmqPV5lFmM2rSbMDMjt2mGxP8hocS2Ph-y5JsoCXdomORLNjwTy-feIe6CaQ6H8vspLQT_pg?key=aj9p8IkJHm6SytSjsbDegnsI)

Follow along with Vincent in the below video, as Vincent steps through the Pick to Tote workflow.

**📹 Video:** https://www.youtube.com/embed/1XFUS-67XSA

▶️ Follow along in the **WMS Mobile App Trail**...next up is [Introducing Scan Move](https://help.cartoncloud.com/knowledge/introducing-scan-move). 🎓

---

<a id="picking-process-on-the-mobile-app-sale-orders"></a>
## Picking process on the mobile app (Sale Orders)

_Source: https://help.cartoncloud.com/knowledge/picking-process-on-the-mobile-app-sale-orders_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Mobile App Trail.**Please ensure you have read [Putaway process on the mobile app (Purchase Orders)](https://help.cartoncloud.com/knowledge/putaway-process-on-the-mobile-app-purchase-orders) first.🎓

Now that you know how to use the Putaway mode on the CartonCloud warehouse mobile application, it is time to start learning about the Picking mode.

The Picking mode on the mobile application is designed to assist you and your team during your warehouse's picking, packing and dispatch process. Using the Picking mode will enable you to pick Sale Orders, verify specific custom fields (for example, batch numbers) upon picking items, and ensure the correct items are picked with the correct quantities and that the order is successfully dispatched from the warehouse. Throughout the process, your customer will be updated with milestone specific notifications (depending on what customer notifications they have set up), and the status of the order will be updated and reflected in the web application. In addition, all associated charges will be automatically calculated, and you can record any necessary adhoc charge data against the order.

### How to access Picking Mode

- Select the hamburger menu icon and select Switch Mode .
- Click the Picking icon.

![](https://help.cartoncloud.com/hs-fs/hubfs/image-png-Mar-25-2026-03-14-56-3979-PM.png?width=200&height=426&name=image-png-Mar-25-2026-03-14-56-3979-PM.png)

- You will now be on the Sale Order List.

### Using the Sale Order List

Once on the Sale Order List page, you will see all the Sale Orders in the given warehouse that are in a status of:

- Awaiting Pick and Pack
- Packing in Progress

The Sale Order must be approved from ‘Draft’ to be visible on the mobile application, and once in a status of ‘Dispatched’, the Sale Order will no longer appear on the mobile application.

The Sale Order status will appear on the far left with a different letter and colour (depending on its status) for each Sale Order.

You can also filter the list by searching for a Sale Order reference, or you can sort the list and split it by customer name, ship date or run sheet.

### Why can’t I see a Sale Order on the Sale Order List?

- Check if the Sale Order has been approved
- Check you have the correct Warehouse selected (from the mobile application settings)

### Picking Process

Now that you understand what the picking process on the CartonCloud mobile app aims to achieve let’s step through how to pick a Sale Order on the mobile app.

Follow along with Vincent as he picks an order in the CartonCloud warehouse using the mobile app.

**📹 Video:** https://www.youtube.com/embed/UfRs-L8vjYI

### Reallocation

Nick from Coffee Warehousing and Distribution is starting to understand how the picking process works on the CartonCloud mobile app. However, Nick would still like to understand how he can substitute stock when picking particular items. In Coffee Warehousing and Distribution pallets are often staked behind each other that are of the same product and they need the ability to take the first pallet from the stack even if CartonCloud instructs them to take the one fifth from the front. With Reallocation, Nick can do just that! Reallocation allows you to change the specific POP (Purchase Order Product) ID that has been allocated to a Sale Order when picking the order via the mobile app. In addition, you can change the unique custom field (for example, the serial number) that is allocated to a Sale Order. This can be configured at both the Customer and product level.

Follow along with Vincent to understand what Reallocation is.

**📹 Video:** https://www.youtube.com/embed/4s0OmgB7UeM

**📹 Video:** https://www.youtube.com/embed/WhHAP-YLz6U

**📹 Video:** https://www.youtube.com/embed/FVhXJQBcxuw

**📹 Video:** https://www.youtube.com/embed/UkfWk6FWsT0

▶️ Follow along in the **WMS Mobile App Trail**...next up is Introducing [Wave Picking on the mobile app](https://help.cartoncloud.com/knowledge/introducing-wave-picking-on-the-mobile-app). 🎓

---

<a id="putaway-process-on-the-mobile-app-purchase-orders"></a>
## Putaway process on the mobile app (Purchase Orders)

_Source: https://help.cartoncloud.com/knowledge/putaway-process-on-the-mobile-app-purchase-orders_

🔔 Note: this article is part of the **CartonCloud Academy - WMS Mobile App Trail.**Please ensure you have read [Introducing the warehouse mobile app](https://help.cartoncloud.com/knowledge/introducing-the-warehouse-mobile-app) first.🎓

Now that you know what the CartonCloud warehouse mobile app is and have it set up on your devices and for your users, it is time to start learning about one of the modes, Putaway!

The Putaway mode on the mobile application is designed to facilitate the inbound or receival process. Using the Putaway mode will allow you to receive Purchase Orders, verify the quantity, products and condition of the goods (e.g. if the freight is damaged) and then put the stock away in the appropriate warehouse location. All the while, your customers will be updated throughout the process (depending on what customer notifications they have set up), the status of the order will be updated and reflected in the web application, and all charges related to the orders will automatically be calculated. In addition, you will be able to scan values against the order (e.g. a batch or SSCC number), print labels and record Adhoc charge data against the order.

### Putaway Process on the Mobile App

![](https://help.cartoncloud.com/hs-fs/hubfs/putaway%20process-png.png?width=311&height=790&name=putaway%20process-png.png)

### How to access Putaway Mode

- Select the hamburger menu icon and select Switch Mode.
- Click the Putaway icon.
- You will now be on the Purchase Order List.

![](https://help.cartoncloud.com/hs-fs/hubfs/Screenshot%202025-12-23%20at%206-20-15%E2%80%AFam-jpeg.jpeg?width=266&height=535&name=Screenshot%202025-12-23%20at%206-20-15%E2%80%AFam-jpeg.jpeg)

### Using the Purchase Order List

Once on the Purchase List page, you will see all the Purchase Orders in the given warehouse that are in a status of:

- Not Yet Received
- Received
- Verified

The Purchase Order must be approved from ‘Draft’ to be visible on the mobile application. Once in a status of ‘Allocated’, the Purchase Order will no longer appear on the mobile application.

The Purchase Order status will appear on the far left with a different letter and colour (depending on its status) for each Purchase Order.

You can also filter the list by searching for a Purchase Order reference, or you can sort the list and split it by customer name.

### Why can’t I see a Purchase Order on the Purchase Order List?

- Check if the Purchase Order has been approved
- Check you have the correct Warehouse selected (from the mobile application settings)

### Receiving the Purchase Order

The first step in the putaway process is to receive the Purchase Order. This step allows you to mark that the Purchase Order has arrived at the warehouse. With the customer notification enabled, this step lets you notify the customer that their goods have arrived at your warehouse.

Follow along with Vincent as he receives a Purchase Order into the CartonCloud warehouse.

**📹 Video:** https://www.youtube.com/embed/XBQ8pokhtL4?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

Once the Purchase Order has been received, the stock can't be allocated to a Sale Order yet. The Purchase Order must be in a 'Allocated' status before the stock can be assigned to a Sale Order.

### Verify and locate a Purchase Order

The next step in the Putaway process is verifying the Purchase Order and then locating it in a warehouse location. Follow along with Vincent as he shows you how to verify and locate a Purchase Order on the mobile app.

**📹 Video:** https://www.youtube.com/embed/9tvF2gTfmj8

Nick is excited to start using the mobile application to verify and locate his Purchase Orders. He wants to use barcode scanning to increment product quantities and fill in required fields such as Batch Number. This will help ensure the correct quantities are counted, and the right Batch Number is recorded for each Purchase Order. To be able to do this, Nick will need to:

- Create Unit of Measure barcodes to scan when verifying the quantity. See this page for steps on how to set this up.
- Set up Purchase Order Product Custom Fields and mark it as required. See this page for steps on how to set this up.

### Inbound unique reference scanning

Now that you know how to receive a Purchase Order, we can go into more detail surrounding some of the options you have when receiving the order. One option you have is to record unique references, for example, serial numbers, by either scanning or inputting the data against the stock coming into the warehouse via the Purchase Order.

Nick from Coffee Warehouse and Distribution will need to follow this process for the majority of his customers as they have requested the team record the serial numbers on the product upon receiving it and verify them on the way out (this will covered in a later module).

#### Benefits of unique reference scanning

- Allows you to record unique references against the base unit of measure (smallest unit of measure) of a product
- Improves tracking accuracy of items
- Allows for data captured on the inbound process to be validated on the outgoing process (as items leave the warehouse)
- More accurate traceability of all items (not just the purchase order as a whole)
- Assist with any recall process or warranty claims
- Provide greater visibility to your customers on their inventory
- Better meet customer requirements for recording custom and unique data against stock

#### Use cases of unique reference scanning

- A pallet comes into a warehouse with 30 individual items and each item needs a serial number scanned against it.
- Wanting to group individual items together on a pallet and use a single pallet barcode to move the items into a warehouse location
- Unloading a container to multiple pallets and locating each pallet to a location

#### Set up requirements

To follow this process in your own CartonCloud account follow the below steps:

- Navigate to the relevant Customer, Contacts > Customers .
- Click Edit.
- Select the Warehouse Management > Purchase Order Products tab.
- From the relevant Custom Field, enable the below settings:
  - Enforce unique values
  - Split to lowest Unit of Measure
  - Make this a required step
- OR you can select Serial Number captured on Inbound and Verified on Outbound from the Configuration Type. Choosing this option will ensure all of the correct settings have been selected.
- Scroll down and select Save .

Please note, Is required can be set to optional at the customer purchase order product custom field but must be required at the product level (for the product you wish to enable inbound unique reference scanning for). To make this change at the product level you will need to edit the relevant product and scroll to the bottom under Modify Purchase Order Product Fields.

#### How to record unique references on inbound

You covered how to receive a Purchase Order in the previous module. In this process, there was a step to record any relevant unique references. The below video steps through this process.

**📹 Video:** https://www.youtube.com/embed/9tvF2gTfmj8

#### How to record unique references against stock that is already in the warehouse

If you already have stock in the warehouse that you wish to record unique references you can do by following the below process. This process is useful when you first start to use unique reference scanning in your operations and you need to record references against existing stock.

**📹 Video:** https://www.youtube.com/embed/P4wcseNVmfU

### Bulk split and bulk split on putaway

Now that you know how to follow the basic putaway process of receiving, verifying and locating, it is time to cover another possible workflow during the putaway process. If you need to break that quantity into pallets or if stock is received damaged and needs to be split onto a different product line so that the status can be updated, you can use the Split or Bulk Split function.

Follow along with Vincent as he demonstrates how to split and bulk split a Purchase Order.

**📹 Video:** https://www.youtube.com/embed/aq0QTmLCWVo?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

Nick knows the Bulk Split option will be useful for his team during the locating process as forklift drivers will be able to locate stock by the pallet rather than having to put multiple pallets into one location.

### Locating the Purchase Order via Scan Move

Even though we have already covered how to locate a Purchase Order, we are going to go through another option you have when locating your Purchase Orders. Depending on your operational processes and workflows, you may choose to have one team receive and verify a Purchase Order and then another team locate it. In this case, locating via Scan Move can be extremely beneficial. Similarly, if you operate a large warehouse where several Purchase Orders are being received at once, and multiple forklifts are moving around the warehouse floor, it can be advantageous to have the ability to split the receiving and locating process.

Follow along with Vincent as he shows you how to locate stock using the Scan Move functionality.

**📹 Video:** https://www.youtube.com/embed/9O2pqjfgLJc?list=PLxs2KBNumIq7mCiWplTg2emZumXyHN2jD

Nick will be encouraging his staff to use Scan Move to locate Purchase Orders, as he usually has one team receiving and verifying the orders and then another putting the orders away. The team putting the orders away can scan the label barcode, take the stock, scan the warehouse location, and put the stock into the warehouse location.

### Pallet Handling

CartonCloud allows you to print, assign and scan pallet labels throughout the system. Pallet labels can be applied when stock arrives, or, to stock already in the warehouse. Pallet labels can be used to locate stock to a location, move stock between locations, to consolidate stock, or to split stock apart.

Pallet labels can be automatically generated when new stock arrives, or pre-printed in bulk and assigned to stock that is arriving. Pallet labels can also be used when picking to specify or verify the stock being picked.

Pallet labels can be printed either from the mobile or web app.

Follow the below video to learn how to apply pallet labels to stock already in your warehouse. This process is well suited if you have just started using pallet labels in your operation.

**📹 Video:** https://www.youtube.com/embed/C3QvsqlrnuQ

### Photos and Documents on Purchase Orders

With Photos and Documents on Purchase Orders, users can attach photos, videos, and documents directly to Purchase Orders through both the mobile and web app. These attachments—whether photos, videos, or documents—are linked to the Purchase Order.

Check out the diagram below for a visual breakdown of how Purchase Orders, Documents, and Attachments are connected.

![](https://help.cartoncloud.com/hs-fs/hubfs/3d7568ebfb798f8bfe22d0563aed49e8_purchase-20-order-png.png?width=670&height=377&name=3d7568ebfb798f8bfe22d0563aed49e8_purchase-20-order-png.png)

Follow along with Vincent as he steps through how to use the Photos and Documents on Purchase Orders via the mobile app in the warehouse.

**📹 Video:** https://www.youtube.com/embed/RvKECtVE8pk

▶️ Follow along in the **WMS Mobile App Trail**...next up is [Picking process on the mobile app (Sale Orders)](https://help.cartoncloud.com/knowledge/picking-process-on-the-mobile-app-sale-orders). 🎓

---
