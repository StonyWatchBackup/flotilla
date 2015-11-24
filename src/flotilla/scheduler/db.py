import logging
from boto.dynamodb2.items import Item

logger = logging.getLogger('flotilla')


class FlotillaSchedulerDynamo(object):
    def __init__(self, assignments, services, status):
        self._assignments = assignments
        self._services = services
        self._status = status

        # TODO: shard scan for multiple schedulers
        self._segments = 1
        self._segment = 0

    def get_revision_weights(self):
        """Load services, revisions and weights"""
        services = {}
        rev_count = 0
        for service in self._services.scan(segment=self._segment,
                                           total_segments=self._segments):
            name = service['service_name']
            del service['service_name']

            service_revs = {k: int(v) for k, v in service.items()}
            services[name] = service_revs
            rev_count += len(service_revs)

        logger.debug('Loaded %s services, %s revisions', len(services),
                     rev_count)
        return services

    def set_assignment(self, service, machine, assignment):
        self._assignments.put_item(data={
            'service_name': service,
            'instance_id': machine,
            'assignment': assignment
        }, overwrite=True)

    def set_assignments(self, assignments):
        """Store assignments in a batch.
        :param assignments: Assignments to store.
        """
        with self._assignments.batch_write() as batch:
            for assignment in assignments:
                batch.put_item(assignment)

    def get_instances(self, service):
        """Get instances and assigned revisions for a service.
        :param service:  Service name.
        :return: Dict of instance id to assigned revision.
        """
        return {a['instance_id']: a
                for a in self._status.query_2(service__eq=service)}

    def get_instance_assignments(self, service):
        """Get instances and assignments for a service
        :param service:  Service name.
        :return: Map of instances of assignments (None if unassigned).
        """
        instances = [i['instance_id'] for i in
                     self._status.query_2(service__eq=service,
                                          attributes=('instance_id',))]

        assignments = {}
        for assignment in self._assignments.batch_get(
                keys=[{'instance_id': i} for i in instances],
                attributes=('instance_id', 'assignment')):
            assignments[assignment['instance_id']] = assignment

        for instance_id in instances:
            if instance_id in assignments:
                continue
            assignments[instance_id] = Item(self._assignments, data={
                'instance_id': instance_id,
                'service': service
            })

        return assignments