
"use strict";

// 1. Wait until the HTML page has loaded
document.addEventListener("DOMContentLoaded", function () {

    // 2. Select all navigation links that point to page sections
    const sectionLinks = document.querySelectorAll(
        '.navbar a[href^="#"]'
    );

    // 3. Add a click event to each section link
    sectionLinks.forEach(function (link) {

        link.addEventListener("click", function (event) {

            // Read the section ID from the link
            const targetId = link.getAttribute("href");

            // Find the matching section
            const targetSection = document.querySelector(targetId);

            // Scroll to it if the section exists
            if (targetSection) {
                event.preventDefault();

                targetSection.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }

        });

    });


    // 4. Display a message when the dashboard link is clicked
    const dashboardLinks = document.querySelectorAll(
        'a[href="/dashboard"], a[href$="/dashboard"]'
    );

    dashboardLinks.forEach(function (link) {

        link.addEventListener("click", function () {
            console.log("Opening the EstateFlow dashboard...");
        });

    });

});

/* ==============================
   ESTATEFLOW PROPERTY SEARCH
============================== */

document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("propertySearch");
    const typeFilter = document.getElementById("typeFilter");
    const listingFilter = document.getElementById("listingFilter");
    const availabilityFilter = document.getElementById("availabilityFilter");
    const tableBody = document.getElementById("propertyTableBody");
    const propertyCount = document.getElementById("propertyCount");
    const noPropertiesMessage = document.getElementById("noPropertiesMessage");

    // Stop if this page doesn't contain the property table.
    if (
        !searchInput ||
        !typeFilter ||
        !listingFilter ||
        !availabilityFilter ||
        !tableBody
    ) {
        return;
    }

    function filterProperties() {
        const searchText = searchInput.value.trim().toLowerCase();
        const selectedType = typeFilter.value;
        const selectedListing = listingFilter.value;
        const selectedStatus = availabilityFilter.value;

        const rows = tableBody.querySelectorAll("tr");
        let visibleCount = 0;

        rows.forEach(function (row) {
            const propertyName = row.dataset.name.toLowerCase();
            const city = row.dataset.city.toLowerCase();
            const type = row.dataset.type;
            const listing = row.dataset.listing;
            const status = row.dataset.status;

            const matchesSearch =
                propertyName.includes(searchText) ||
                city.includes(searchText);

            const matchesType =
                selectedType === "" || type === selectedType;

            const matchesListing =
                selectedListing === "" || listing === selectedListing;

            const matchesStatus =
                selectedStatus === "" || status === selectedStatus;

            const isVisible =
                matchesSearch &&
                matchesType &&
                matchesListing &&
                matchesStatus;

            row.hidden = !isVisible;

            if (isVisible) {
                visibleCount++;
            }
        });

        propertyCount.textContent =
            visibleCount + (visibleCount === 1 ? " property" : " properties");

        noPropertiesMessage.hidden = visibleCount !== 0;
    }

    searchInput.addEventListener("input", filterProperties);
    typeFilter.addEventListener("change", filterProperties);
    listingFilter.addEventListener("change", filterProperties);
    availabilityFilter.addEventListener("change", filterProperties);

    // Set the initial count.
    filterProperties();
});

/* ==============================
   ESTATEFLOW CUSTOMER SEARCH
============================== */

document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("customerSearch");
    const typeFilter = document.getElementById("customerTypeFilter");
    const tableBody = document.getElementById("customerTableBody");
    const customerCount = document.getElementById("customerCount");
    const noCustomersMessage = document.getElementById("noCustomersMessage");

    // Run only on the Customers page.
    if (!searchInput || !typeFilter || !tableBody) {
        return;
    }

    function filterCustomers() {
        const searchText = searchInput.value.trim().toLowerCase();
        const selectedType = typeFilter.value;

        const rows = tableBody.querySelectorAll("tr");
        let visibleCount = 0;

        rows.forEach(function (row) {
            const name = row.dataset.name.toLowerCase();
            const phone = row.dataset.phone.toLowerCase();
            const email = row.dataset.email.toLowerCase();
            const type = row.dataset.type;

            const matchesSearch =
                name.includes(searchText) ||
                phone.includes(searchText) ||
                email.includes(searchText);

            const matchesType =
                selectedType === "" || type === selectedType;

            const isVisible = matchesSearch && matchesType;

            row.hidden = !isVisible;

            if (isVisible) {
                visibleCount++;
            }
        });

        customerCount.textContent =
            visibleCount + (visibleCount === 1 ? " customer" : " customers");

        noCustomersMessage.hidden = visibleCount !== 0;
    }

    searchInput.addEventListener("input", filterCustomers);
    typeFilter.addEventListener("change", filterCustomers);

    filterCustomers();
});



/* ==============================
   CUSTOMER FORM VALIDATION
============================== */

document.addEventListener("DOMContentLoaded", function () {
    const customerForm = document.getElementById("addCustomerForm");

    if (!customerForm) {
        return;
    }

    customerForm.addEventListener("submit", function (event) {
        const phone = document.getElementById("customerPhone").value.trim();

        if (!/^[0-9]{10}$/.test(phone)) {
            event.preventDefault();
            alert("Please enter a valid 10-digit phone number.");
        }

        // If the phone number is valid, allow the form
        // to submit normally to Flask.
    });
});

/* ==============================
   ESTATEFLOW SITE VISITS
============================== */

document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("visitSearch");
    const statusFilter = document.getElementById("visitStatusFilter");
    const tableBody = document.getElementById("visitTableBody");
    const visitCount = document.getElementById("visitCount");
    const noVisitsMessage = document.getElementById("noVisitsMessage");

    // Run only on the Site Visits page.
    if (!searchInput || !statusFilter || !tableBody) {
        return;
    }

    function filterVisits() {
        const searchText = searchInput.value.trim().toLowerCase();
        const selectedStatus = statusFilter.value;
        const rows = tableBody.querySelectorAll("tr");

        let visibleCount = 0;

        rows.forEach(function (row) {
            const customer = row.dataset.customer.toLowerCase();
            const property = row.dataset.property.toLowerCase();
            const status = row.dataset.status;

            const matchesSearch =
                customer.includes(searchText) ||
                property.includes(searchText);

            const matchesStatus =
                selectedStatus === "" || status === selectedStatus;

            const isVisible = matchesSearch && matchesStatus;

            row.hidden = !isVisible;

            if (isVisible) {
                visibleCount++;
            }
        });

        visitCount.textContent =
            visibleCount + (visibleCount === 1 ? " visit" : " visits");

        noVisitsMessage.hidden = visibleCount !== 0;
    }

    searchInput.addEventListener("input", filterVisits);
    statusFilter.addEventListener("change", filterVisits);

    filterVisits();
});



/* ==============================
   SITE VISIT FORM VALIDATION
============================== */

document.addEventListener("DOMContentLoaded", function () {
    const visitForm = document.getElementById("addVisitForm");

    if (!visitForm) {
        return;
    }

    visitForm.addEventListener("submit", function (event) {
        const date = document.getElementById("visitDate").value;

        if (!date) {
            event.preventDefault();
            alert("Please select a visit date.");
            return;
        }

        const selectedDate = new Date(date + "T00:00:00");
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        if (selectedDate < today) {
            event.preventDefault();
            alert("Please select today or a future date.");
        }

        // Valid forms submit normally to Flask.
    });
});
/* ==============================
   ESTATEFLOW RENTALS SEARCH
============================== */

document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("rentalSearch");
    const statusFilter = document.getElementById("rentalStatusFilter");
    const tableBody = document.getElementById("rentalTableBody");
    const rentalCount = document.getElementById("rentalCount");
    const noRentalsMessage = document.getElementById("noRentalsMessage");

    // Run only on the Rentals page.
    if (!searchInput || !statusFilter || !tableBody) {
        return;
    }

    function filterRentals() {
        const searchText = searchInput.value.trim().toLowerCase();
        const selectedStatus = statusFilter.value;
        const rows = tableBody.querySelectorAll("tr");

        let visibleCount = 0;

        rows.forEach(function (row) {
            const tenant = row.dataset.tenant.toLowerCase();
            const property = row.dataset.property.toLowerCase();
            const status = row.dataset.status;

            const matchesSearch =
                tenant.includes(searchText) ||
                property.includes(searchText);

            const matchesStatus =
                selectedStatus === "" || status === selectedStatus;

            const isVisible = matchesSearch && matchesStatus;

            row.hidden = !isVisible;

            if (isVisible) {
                visibleCount++;
            }
        });

        rentalCount.textContent =
            visibleCount + (visibleCount === 1 ? " rental" : " rentals");

        noRentalsMessage.hidden = visibleCount !== 0;
    }

    searchInput.addEventListener("input", filterRentals);
    statusFilter.addEventListener("change", filterRentals);

    filterRentals();
});



rentalForm.addEventListener("submit", function (event) {
    const tenant = document.getElementById("rentalTenant").value.trim();
    const property = document.getElementById("rentalProperty").value.trim();

    const rent = Number(document.getElementById("monthlyRent").value);
    const deposit = Number(document.getElementById("securityDeposit").value);

    const startDate = document.getElementById("agreementStart").value;
    const endDate = document.getElementById("agreementEnd").value;

    if (!tenant || !property || !startDate || !endDate) {
        event.preventDefault();
        message.textContent = "Please complete all required fields.";
        return;
    }

    if (rent <= 0 || deposit < 0) {
        event.preventDefault();
        message.textContent =
            "Rent must be greater than zero and deposit cannot be negative.";
        return;
    }

    if (endDate <= startDate) {
        event.preventDefault();
        message.textContent =
            "Agreement end date must be after the start date.";
        return;
    }



});