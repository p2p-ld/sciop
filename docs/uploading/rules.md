# Rules

{% if config.extra.instance_config %}
{% for rule in config.extra.instance_config.rules %}
## {{ rule.title }}

{{ rule.description }}
{% endfor %} 
{% endif %}