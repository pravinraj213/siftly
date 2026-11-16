variable "region" {
  type    = string
  default = "us-east-1"
}
variable "function_name" {
  type        = string
  default     = "siftly-moderate"
  description = "Lambda name; use a unique siftly- prefix for each deployment."
  validation {
    condition     = can(regex("^siftly-[A-Za-z0-9_-]+$", var.function_name))
    error_message = "Function name must start with siftly-."
  }
}
variable "blocked_categories" {
  type    = string
  default = "Explicit,Non-Explicit Nudity of Intimate parts and Kissing,Swimwear or Underwear,Violence,Visually Disturbing"
}
variable "moderation_confidence" {
  type    = number
  default = 70
  validation {
    condition     = var.moderation_confidence >= 0 && var.moderation_confidence <= 100
    error_message = "Confidence must be between 0 and 100."
  }
}

variable "reserved_concurrency" {
  type        = number
  default     = null
  nullable    = true
  description = "Optional function reservation. Leave null for accounts with limited unreserved concurrency."
  validation {
    condition     = var.reserved_concurrency == null ? true : var.reserved_concurrency >= 0 && floor(var.reserved_concurrency) == var.reserved_concurrency
    error_message = "Reserved concurrency must be null or a nonnegative integer."
  }
}
