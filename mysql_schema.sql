-- MySQL dump 10.13  Distrib 9.3.0, for Win64 (x86_64)
--
-- Host: localhost    Database: milla99
-- ------------------------------------------------------
-- Server version	9.3.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `administrador`
--

DROP TABLE IF EXISTS `administrador`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `administrador` (
  `id` char(32) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  UNIQUE KEY `ix_administrador_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `client_request`
--

DROP TABLE IF EXISTS `client_request`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_request` (
  `id` char(32) NOT NULL,
  `id_client` char(32) NOT NULL,
  `id_driver_assigned` char(32) DEFAULT NULL,
  `type_service_id` int NOT NULL,
  `payment_method_id` int DEFAULT 1,
  `fare_offered` float DEFAULT NULL,
  `fare_assigned` float DEFAULT NULL,
  `penality` float DEFAULT 0,
  `pickup_description` varchar(255) DEFAULT NULL,
  `destination_description` varchar(255) DEFAULT NULL,
  `review` varchar(255) DEFAULT NULL,
  `client_rating` float DEFAULT NULL,
  `driver_rating` float DEFAULT NULL,
  `status` enum('CREATED','PENDING','ACCEPTED','ON_THE_WAY','ARRIVED','TRAVELLING','FINISHED','PAID','CANCELLED') DEFAULT NULL,
  `pickup_position` point NOT NULL /*!80003 SRID 4326 */,
  `destination_position` point NOT NULL /*!80003 SRID 4326 */,
  `assigned_busy_driver_id` char(32) DEFAULT NULL,
  `estimated_pickup_time` datetime DEFAULT NULL,
  `driver_current_trip_remaining_time` float DEFAULT NULL,
  `driver_transit_time` float DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `id_client` (`id_client`),
  KEY `id_driver_assigned` (`id_driver_assigned`),
  KEY `type_service_id` (`type_service_id`),
  KEY `payment_method_id` (`payment_method_id`),
  KEY `assigned_busy_driver_id` (`assigned_busy_driver_id`),
  SPATIAL KEY `pickup_position` (`pickup_position`),
  SPATIAL KEY `destination_position` (`destination_position`),
  CONSTRAINT `client_request_ibfk_1` FOREIGN KEY (`id_client`) REFERENCES `user` (`id`),
  CONSTRAINT `client_request_ibfk_2` FOREIGN KEY (`id_driver_assigned`) REFERENCES `user` (`id`),
  CONSTRAINT `client_request_ibfk_3` FOREIGN KEY (`type_service_id`) REFERENCES `type_service` (`id`),
  CONSTRAINT `client_request_ibfk_4` FOREIGN KEY (`payment_method_id`) REFERENCES `payment_method` (`id`),
  CONSTRAINT `client_request_ibfk_5` FOREIGN KEY (`assigned_busy_driver_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `company_account`
--

DROP TABLE IF EXISTS `company_account`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `company_account` (
  `id` char(32) NOT NULL,
  `income` int DEFAULT NULL,
  `expense` int DEFAULT NULL,
  `type` enum('SERVICE','WITHDRAWS','ADDITIONAL') NOT NULL,
  `client_request_id` char(32) DEFAULT NULL,
  `date` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `client_request_id` (`client_request_id`),
  CONSTRAINT `company_account_ibfk_1` FOREIGN KEY (`client_request_id`) REFERENCES `client_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `config_service_value`
--

DROP TABLE IF EXISTS `config_service_value`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `config_service_value` (
  `id` int NOT NULL AUTO_INCREMENT,
  `km_value` float NOT NULL,
  `min_value` float NOT NULL,
  `tarifa_value` float DEFAULT NULL,
  `weight_value` float DEFAULT NULL,
  `service_type_id` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `service_type_id` (`service_type_id`),
  CONSTRAINT `config_service_value_ibfk_1` FOREIGN KEY (`service_type_id`) REFERENCES `type_service` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `document_type`
--

DROP TABLE IF EXISTS `document_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `document_type` (
  `name` varchar(255) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_documents`
--

DROP TABLE IF EXISTS `driver_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_documents` (
  `document_type_id` int NOT NULL,
  `document_front_url` varchar(255) DEFAULT NULL,
  `document_back_url` varchar(255) DEFAULT NULL,
  `status` enum('PENDING','APPROVED','REJECTED','EXPIRED') NOT NULL,
  `expiration_date` datetime DEFAULT NULL,
  `id` char(32) NOT NULL,
  `driver_info_id` char(32) NOT NULL,
  `vehicle_info_id` char(32) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `document_type_id` (`document_type_id`),
  KEY `driver_info_id` (`driver_info_id`),
  KEY `vehicle_info_id` (`vehicle_info_id`),
  CONSTRAINT `driver_documents_ibfk_1` FOREIGN KEY (`document_type_id`) REFERENCES `document_type` (`id`),
  CONSTRAINT `driver_documents_ibfk_2` FOREIGN KEY (`driver_info_id`) REFERENCES `driver_info` (`id`),
  CONSTRAINT `driver_documents_ibfk_3` FOREIGN KEY (`vehicle_info_id`) REFERENCES `vehicle_info` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_info`
--

DROP TABLE IF EXISTS `driver_info`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_info` (
  `first_name` varchar(255) NOT NULL,
  `last_name` varchar(255) NOT NULL,
  `birth_date` date NOT NULL,
  `email` varchar(255) DEFAULT NULL,
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `pending_request_id` char(32) DEFAULT NULL,
  `pending_request_accepted_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `pending_request_id` (`pending_request_id`),
  CONSTRAINT `driver_info_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `driver_info_ibfk_2` FOREIGN KEY (`pending_request_id`) REFERENCES `client_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_position`
--

DROP TABLE IF EXISTS `driver_position`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_position` (
  `id_driver` char(32) NOT NULL,
  `position` point NOT NULL /*!80003 SRID 4326 */,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id_driver`),
  SPATIAL KEY `position` (`position`),
  CONSTRAINT `driver_position_ibfk_1` FOREIGN KEY (`id_driver`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_savings`
--

DROP TABLE IF EXISTS `driver_savings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_savings` (
  `id` char(32) NOT NULL,
  `mount` int DEFAULT NULL,
  `user_id` char(32) NOT NULL,
  `status` enum('SAVING','APPROVED') NOT NULL,
  `date_saving` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `driver_savings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_trip_offer`
--

DROP TABLE IF EXISTS `driver_trip_offer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_trip_offer` (
  `id` char(32) NOT NULL,
  `id_driver` char(32) NOT NULL,
  `id_client_request` char(32) NOT NULL,
  `fare_offer` float NOT NULL,
  `time` float NOT NULL,
  `distance` float NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `id_driver` (`id_driver`),
  KEY `id_client_request` (`id_client_request`),
  CONSTRAINT `driver_trip_offer_ibfk_1` FOREIGN KEY (`id_driver`) REFERENCES `user` (`id`),
  CONSTRAINT `driver_trip_offer_ibfk_2` FOREIGN KEY (`id_client_request`) REFERENCES `client_request` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `project_settings`
--

DROP TABLE IF EXISTS `project_settings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `project_settings` (
  `driver_dist` varchar(255) NOT NULL,
  `referral_1` varchar(255) NOT NULL,
  `referral_2` varchar(255) NOT NULL,
  `referral_3` varchar(255) NOT NULL,
  `referral_4` varchar(255) NOT NULL,
  `referral_5` varchar(255) NOT NULL,
  `driver_saving` varchar(255) NOT NULL,
  `company` varchar(255) NOT NULL,
  `bonus` varchar(255) NOT NULL,
  `amount` varchar(255) NOT NULL,
  `fine_one` varchar(255) DEFAULT NULL,
  `fine_two` varchar(255) DEFAULT NULL,
  `cancel_max_days` int DEFAULT NULL,
  `cancel_max_weeks` int DEFAULT NULL,
  `day_suspension` int DEFAULT NULL,
  `request_timeout_minutes` int DEFAULT 5,
  `max_wait_time_for_busy_driver` float DEFAULT 15.0,
  `max_distance_for_busy_driver` float DEFAULT 2.0,
  `max_transit_time_for_busy_driver` float DEFAULT 5.0,
  `id` int NOT NULL AUTO_INCREMENT,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `referral`
--

DROP TABLE IF EXISTS `referral`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `referral` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `referred_by_id` char(32) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `referred_by_id` (`referred_by_id`),
  CONSTRAINT `referral_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `referral_ibfk_2` FOREIGN KEY (`referred_by_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `role`
--

DROP TABLE IF EXISTS `role`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `role` (
  `id` varchar(36) NOT NULL,
  `name` varchar(36) NOT NULL,
  `route` varchar(255) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_role_name` (`name`),
  KEY `ix_role_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `transaction`
--

DROP TABLE IF EXISTS `transaction`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `transaction` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `income` int DEFAULT NULL,
  `expense` int DEFAULT NULL,
  `type` enum('BONUS','SERVICE','RECHARGE','REFERRAL_1','REFERRAL_2','REFERRAL_3','REFERRAL_4','REFERRAL_5','WITHDRAWAL','SAVING_BALANCE','BALANCE') NOT NULL,
  `client_request_id` char(32) DEFAULT NULL,
  `id_withdrawal` char(32) DEFAULT NULL,
  `is_confirmed` tinyint(1) NOT NULL,
  `date` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `client_request_id` (`client_request_id`),
  KEY `id_withdrawal` (`id_withdrawal`),
  CONSTRAINT `transaction_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
  CONSTRAINT `transaction_ibfk_2` FOREIGN KEY (`client_request_id`) REFERENCES `client_request` (`id`),
  CONSTRAINT `transaction_ibfk_3` FOREIGN KEY (`id_withdrawal`) REFERENCES `withdrawal` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `type_service`
--

DROP TABLE IF EXISTS `type_service`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `type_service` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `vehicle_type_id` int NOT NULL,
  `allowed_role` enum('DRIVER','CLIENT','ADMIN') NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `vehicle_type_id` (`vehicle_type_id`),
  CONSTRAINT `type_service_ibfk_1` FOREIGN KEY (`vehicle_type_id`) REFERENCES `vehicle_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user`
--

DROP TABLE IF EXISTS `user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user` (
  `full_name` varchar(255) DEFAULT NULL,
  `country_code` varchar(255) NOT NULL,
  `phone_number` varchar(255) NOT NULL,
  `is_verified_phone` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `id` char(32) NOT NULL,
  `selfie_url` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_has_role`
--

DROP TABLE IF EXISTS `user_has_role`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_has_role` (
  `id_user` char(32) NOT NULL,
  `id_rol` varchar(255) NOT NULL,
  `is_verified` tinyint(1) NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED','EXPIRED') NOT NULL,
  `verified_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id_user`,`id_rol`),
  KEY `id_rol` (`id_rol`),
  CONSTRAINT `user_has_role_ibfk_1` FOREIGN KEY (`id_user`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_has_role_ibfk_2` FOREIGN KEY (`id_rol`) REFERENCES `role` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vehicle_info`
--

DROP TABLE IF EXISTS `vehicle_info`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `vehicle_info` (
  `brand` varchar(255) NOT NULL,
  `model` varchar(255) NOT NULL,
  `model_year` int NOT NULL,
  `color` varchar(255) NOT NULL,
  `plate` varchar(255) NOT NULL,
  `vehicle_type_id` int NOT NULL,
  `id` char(32) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `driver_info_id` char(32) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `vehicle_type_id` (`vehicle_type_id`),
  KEY `driver_info_id` (`driver_info_id`),
  CONSTRAINT `vehicle_info_ibfk_1` FOREIGN KEY (`vehicle_type_id`) REFERENCES `vehicle_type` (`id`),
  CONSTRAINT `vehicle_info_ibfk_2` FOREIGN KEY (`driver_info_id`) REFERENCES `driver_info` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `vehicle_type`
--

DROP TABLE IF EXISTS `vehicle_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `vehicle_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `capacity` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_vehicle_type_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `verification`
--

DROP TABLE IF EXISTS `verification`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `verification` (
  `user_id` char(32) NOT NULL,
  `verification_code` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `is_verified` tinyint(1) NOT NULL,
  `attempts` int NOT NULL,
  `id` char(32) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `verification_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `verify_mount`
--

DROP TABLE IF EXISTS `verify_mount`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `verify_mount` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `mount` int NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `verify_mount_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `withdrawal`
--

DROP TABLE IF EXISTS `withdrawal`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `withdrawal` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `amount` int NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED') NOT NULL,
  `withdrawal_date` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `withdrawal_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `payment_method`
--

DROP TABLE IF EXISTS `payment_method`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `payment_method` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bank`
--

DROP TABLE IF EXISTS `bank`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank` (
  `id` int NOT NULL AUTO_INCREMENT,
  `bank_code` varchar(10) NOT NULL,
  `bank_name` varchar(100) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `bank_code` (`bank_code`),
  KEY `ix_bank_id` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `bank_account`
--

DROP TABLE IF EXISTS `bank_account`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `bank_account` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `bank_id` int NOT NULL,
  `account_type` enum('savings','checking') NOT NULL,
  `account_holder_name` varchar(255) NOT NULL,
  `account_number` varchar(255) NOT NULL,
  `identification_number` varchar(255) NOT NULL,
  `type_identification` enum('CC','CE','NIT') NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `verification_date` datetime DEFAULT NULL,
  `last_used_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `bank_id` (`bank_id`),
  CONSTRAINT `bank_account_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `bank_account_ibfk_2` FOREIGN KEY (`bank_id`) REFERENCES `bank` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_cancellation`
--

DROP TABLE IF EXISTS `driver_cancellation`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_cancellation` (
  `id` char(32) NOT NULL,
  `id_driver` char(32) NOT NULL,
  `id_client_request` char(32) NOT NULL,
  `cancelled_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `id_driver` (`id_driver`),
  KEY `id_client_request` (`id_client_request`),
  KEY `idx_driver_cancellation_date` (`id_driver`, `cancelled_at`),
  CONSTRAINT `driver_cancellation_ibfk_1` FOREIGN KEY (`id_driver`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `driver_cancellation_ibfk_2` FOREIGN KEY (`id_client_request`) REFERENCES `client_request` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `penality_user`
--

DROP TABLE IF EXISTS `penality_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `penality_user` (
  `id` char(32) NOT NULL,
  `id_client_request` char(32) NOT NULL,
  `id_user` char(32) NOT NULL,
  `id_driver_assigned` char(32) NOT NULL,
  `id_driver_get_money` char(32) DEFAULT NULL,
  `amount` float NOT NULL,
  `status` enum('PENDING','PAID') NOT NULL DEFAULT 'PENDING',
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `id_client_request` (`id_client_request`),
  KEY `id_user` (`id_user`),
  KEY `id_driver_assigned` (`id_driver_assigned`),
  KEY `id_driver_get_money` (`id_driver_get_money`),
  CONSTRAINT `penality_user_ibfk_1` FOREIGN KEY (`id_client_request`) REFERENCES `client_request` (`id`) ON DELETE CASCADE,
  CONSTRAINT `penality_user_ibfk_2` FOREIGN KEY (`id_user`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `penality_user_ibfk_3` FOREIGN KEY (`id_driver_assigned`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `penality_user_ibfk_4` FOREIGN KEY (`id_driver_get_money`) REFERENCES `user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `user_fcm_token`
--

DROP TABLE IF EXISTS `user_fcm_token`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_fcm_token` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `fcm_token` varchar(512) NOT NULL,
  `device_type` varchar(20) NOT NULL,
  `device_name` varchar(100) DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `last_used` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `user_fcm_token_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_message`
--

DROP TABLE IF EXISTS `chat_message`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_message` (
  `id` char(36) NOT NULL,
  `sender_id` char(36) NOT NULL,
  `receiver_id` char(36) NOT NULL,
  `client_request_id` char(36) NOT NULL,
  `message` varchar(500) NOT NULL,
  `status` enum('SENT','DELIVERED','READ','FAILED') NOT NULL DEFAULT 'SENT',
  `is_read` tinyint(1) NOT NULL DEFAULT 0,
  `expires_at` datetime NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_sender_id` (`sender_id`),
  KEY `idx_receiver_id` (`receiver_id`),
  KEY `idx_client_request_id` (`client_request_id`),
  KEY `idx_expires_at` (`expires_at`),
  KEY `idx_created_at` (`created_at`),
  CONSTRAINT `fk_chat_message_sender` FOREIGN KEY (`sender_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_chat_message_receiver` FOREIGN KEY (`receiver_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_chat_message_client_request` FOREIGN KEY (`client_request_id`) REFERENCES `client_request` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `refresh_token`
--

DROP TABLE IF EXISTS `refresh_token`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `refresh_token` (
  `id` char(32) NOT NULL,
  `user_id` char(32) NOT NULL,
  `token_hash` varchar(255) NOT NULL,
  `expires_at` datetime NOT NULL,
  `is_revoked` tinyint(1) NOT NULL DEFAULT '0',
  `user_agent` varchar(500) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id` (`id`),
  KEY `user_id` (`user_id`),
  KEY `token_hash` (`token_hash`),
  KEY `expires_at` (`expires_at`),
  KEY `is_revoked` (`is_revoked`),
  CONSTRAINT `refresh_token_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

-- Crear índices adicionales para optimizar consultas de chat
CREATE INDEX `idx_unread_messages` ON `chat_message` (`receiver_id`, `is_read`, `created_at`);
CREATE INDEX `idx_conversation_messages` ON `chat_message` (`client_request_id`, `created_at`);

-- Crear evento para limpiar mensajes expirados automáticamente
DELIMITER $$
CREATE EVENT IF NOT EXISTS `cleanup_expired_chat_messages`
ON SCHEDULE EVERY 1 DAY
STARTS CURRENT_TIMESTAMP
DO
BEGIN
    DELETE FROM `chat_message` 
    WHERE `expires_at` < NOW();
END$$
DELIMITER ;

-- Habilitar el event scheduler si no está habilitado
SET GLOBAL event_scheduler = ON;

/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-05-29 16:10:49
