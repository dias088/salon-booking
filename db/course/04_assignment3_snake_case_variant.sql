SELECT service_id, service_name, category, price, duration_minutes
FROM services
WHERE category IN ('Coloring', 'Care')
  AND price > 10000
ORDER BY price DESC;
 
SELECT appointment_id, client_id, stylist_id, appointment_date, status
FROM appointments
WHERE appointment_date BETWEEN '2026-06-01' AND '2026-08-31 23:59:59'
  AND status = 'Completed'
ORDER BY appointment_date;
 

SELECT client_id, first_name, last_name, email
FROM clients
WHERE email ILIKE '%@gmail.com'
ORDER BY last_name;
 

SELECT stylist_id, first_name, last_name, specialization, salary
FROM stylists
WHERE is_active = TRUE
  AND salary >= 300000
ORDER BY salary DESC;
 

SELECT appointment_id, client_id, appointment_date, status
FROM appointments
WHERE status IN ('Cancelled', 'No-show')
ORDER BY appointment_date;
